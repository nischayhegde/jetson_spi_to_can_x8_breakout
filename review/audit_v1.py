"""Inspect the exported V1 netlist without changing the KiCad project."""

import csv
import hashlib
import itertools
import json
from collections import Counter
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent / "breakout" / "breakout.kicad_sch"
netlist = ET.parse(ROOT / "breakout.net.xml").getroot()
pin_net = {}
for net in netlist.findall("./nets/net"):
    for node in net.findall("node"):
        pin_net[(node.attrib["ref"], node.attrib["pin"])] = net.attrib["name"]


def net(ref, pin):
    return pin_net.get((ref, str(pin)), "MISSING")


rows = []
for channel, number in enumerate(range(9, 17), 1):
    ref = f"U{number}"
    rows.append({
        "channel": channel,
        "reference": ref,
        "expected_spi": 0 if channel <= 4 else 1,
        "VDD_pin14": net(ref, 14),
        "VIO_pin1": net(ref, 1),
        "VCC_pin25": net(ref, 25),
        "SCK_pin9": net(ref, 9),
        "SDI_pin10": net(ref, 10),
        "SDO_pin11": net(ref, 11),
        "SDO_series_resistor": [2, 9, 12, 15, 22, 25, 28, 31][channel - 1],
        "CS_pin13": net(ref, 13),
        "INT_pin19": net(ref, 19),
        "TXCAN15_to_TXD23": net(ref, 15) == net(ref, 23),
        "RXD28_to_RXCAN16": net(ref, 28) == net(ref, 16),
        "STBY_pin5": net(ref, 5),
        "VSS_pin22": net(ref, 22),
        "GND_pin24": net(ref, 24),
        "crystal_pad2": net(f"Y{channel}", 2),
        "crystal_pad4": net(f"Y{channel}", 4),
    })

with (ROOT / "channel_audit.csv").open("w", newline="", encoding="utf-8-sig") as output:
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)

# Follow the actual gate input/output net names, including the four inverters
# and two OR packages. This captures the user's V1 mapping, not the old BOM's
# NOT-AND-NOT equations.
gates = {}
for ref in ("U1", "U5"):
    for a, b, y in ((1, 2, 3), (4, 5, 6), (9, 10, 8), (12, 13, 11)):
        gates[net(ref, y)] = ("OR", net(ref, a), net(ref, b))
for a, y in ((1, 2), (3, 4), (5, 6), (9, 8)):
    gates[net("U2", y)] = ("NOT", net("U2", a))


def evaluate(name, signals):
    if name in signals:
        return signals[name]
    kind, *inputs = gates[name]
    values = [evaluate(value, signals) for value in inputs]
    return int(not values[0]) if kind == "NOT" else int(any(values))


bank_tables = []
for bus, bank_pin, first in ((0, "GPIO_7", 1), (1, "GPIO_11", 5)):
    for bank, cs0, cs1 in itertools.product((0, 1), repeat=3):
        signals = {bank_pin: bank, f"SPI{bus}_CS0": cs0, f"SPI{bus}_CS1": cs1}
        levels = {f"CAN{n}_CS": evaluate(f"CAN{n}_CS", signals) for n in range(first, first + 4)}
        bank_tables.append({
            "spi": bus, "bank": bank, "native_cs0": cs0, "native_cs1": cs1,
            "forbidden_both_cs_active": cs0 == cs1 == 0,
            "gate_output_levels": levels,
            "selected_logical_channels": [name for name, level in levels.items() if level == 0],
        })

irq_table = []
for levels in itertools.product((0, 1), repeat=8):
    irq_table.append({"can_nINT_levels": levels, "U4_pin8": int(not all(levels))})

violations = [v for sheet in json.loads((ROOT / "erc.json").read_text())["sheets"] for v in sheet["violations"]]
components = netlist.findall("./components/comp")
summary = {
    "schematic_sha256": hashlib.sha256(PROJECT.read_bytes()).hexdigest(),
    "components": len(components),
    "can_controllers": len(rows),
    "missing_footprints": [c.attrib["ref"] for c in components if not c.findtext("footprint")],
    "erc_total": len(violations),
    "erc_severity_counts": dict(Counter(v["severity"] for v in violations)),
    "erc_type_counts": dict(Counter(v["type"] for v in violations)),
    "channel_audit": rows,
    "gate_truth_tables": bank_tables,
    "irq_truth_table": irq_table,
    "bank_idle_deselects_all": all(
        all(v == 1 for v in row["gate_output_levels"].values())
        for row in bank_tables if row["native_cs0"] == row["native_cs1"] == 1
    ),
    "one_native_cs_selects_one_logical_output": all(
        len(row["selected_logical_channels"]) == 1
        for row in bank_tables if row["native_cs0"] != row["native_cs1"]
    ),
    "warning": "Correct logical gate outputs do not fix the CAN5/CAN6 copied CS labels or the SPI/power wiring errors.",
}
(ROOT / "audit_results.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps({key: value for key, value in summary.items() if key not in (
    "missing_footprints", "channel_audit", "gate_truth_tables", "irq_truth_table"
)}, indent=2))
print("Components without footprint assignments:", len(summary["missing_footprints"]))
