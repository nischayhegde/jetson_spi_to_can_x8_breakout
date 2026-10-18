'''Render the active nonisolated BOM, references, CAD mapping and review notes.'''
from pathlib import Path
import csv
import hashlib
import json
import re
import shutil
import sys

from library_usage import active_selection

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
REVIEW = REPO / 'review' / 'latest'
SCHEMATIC = REPO / 'breakout' / 'breakout.kicad_sch'
TARGET = REPO / 'componentlist.md.txt'


def ref_key(ref):
    match = re.match(r'(.*?)(\d+)$', ref)
    return (match[1], int(match[2])) if match else (ref, 0)


def display_refs(refs):
    if len(refs) > 20:
        return f'{len(refs)} bypass capacitors; exact references in CSV'
    result = []
    i = 0
    while i < len(refs):
        end = i
        while end + 1 < len(refs):
            prefix, number = ref_key(refs[end])
            next_prefix, next_number = ref_key(refs[end + 1])
            if prefix != next_prefix or next_number != number + 1:
                break
            end += 1
        result.append(refs[i] if end == i else refs[i] + '-' + refs[end])
        i = end + 1
    return ', '.join(result) or 'F2 (to add)'


DETAILS = {
    'MCP251863T-E/SS': ('Microchip', 'CAN controller/transceiver', 'SPI CAN FD controller plus transceiver; SSOP-28; VDD/VIO=3.3 V, VCC=5 V'),
    'ABM8G-40.000MHZ-18-D2Y-T': ('Abracon', '40 MHz crystal', 'Passive crystal; CL=18 pF; grounded case pads; 3.2 x 2.5 mm'),
    'TLV75533PDBVR': ('Texas Instruments', '3.3 V LDO', 'Fixed 3.3 V, 500 mA; SOT-23-5 / DBV'),
    'CL10C270JB8NNNC': ('Samsung Electro-Mechanics', 'Crystal load capacitor', '27 pF, +/-5%, C0G/NP0, 50 V, 0603'),
    'CC0603KRX7R9BB104': ('YAGEO', 'Local bypass capacitor', '100 nF, +/-10%, X7R, 50 V, 0603'),
    'CGA3E1X7R1E105K080AC': ('TDK', 'LDO input/output capacitor', '1 uF, +/-10%, X7R, 25 V, 0603'),
    'CL21B106KOQNNNE': ('Samsung Electro-Mechanics', 'Protected-input bulk capacitor', '10 uF, +/-10%, X7R, 16 V, 0805; see availability note'),
    'RC1206FR-07120RL': ('YAGEO', 'Fixed CAN termination', '120 ohm, +/-1%, 0.25 W, 1206'),
    'RC0603FR-0710KL': ('YAGEO', 'CAN nCS pull-ups / MOSFET gate pull-down', '10 kohm, +/-1%, 0.1 W, 0603'),
    'RC0603FR-07100KL': ('YAGEO', 'Native Jetson CS pull-ups', '100 kohm, +/-1%, 0.1 W, 0603'),
    'RC0603FR-0733RL': ('YAGEO', 'SPI series damping', '33 ohm, +/-1%, 0.1 W, 0603'),
    'B3B-XH-A': ('JST', 'CAN connector', '3 positions, 2.50 mm pitch, vertical through-hole XH header'),
    'B2B-XH-A': ('JST', '5 V input connector', '2 positions, 2.50 mm pitch, vertical through-hole XH header'),
    'M20-9982046': ('Harwin', 'Jetson harness header', '2 x 20, 2.54 mm pitch, male vertical through-hole header'),
    '0466001.NR': ('Littelfuse', 'Series input fuse - ADD', '1 A, 63 V AC/DC, fast acting, 1206; load/temperature qualification required'),
    'AO3401A': ('Alpha & Omega Semiconductor', 'Reverse-hookup MOSFET', 'P-channel, -30 V, VGS absolute maximum +/-12 V, SOT-23'),
    'BZT52C6V8-13-F': ('Diodes Incorporated', 'MOSFET gate-source clamp', '6.8 V Zener, SOD-123; not a 5 V rail clamp'),
    '74AHC30PW,118': ('Nexperia', 'Shared interrupt NAND', '8-input NAND, TSSOP-14; powered at 3.3 V'),
    '74LVC32APW,118': ('Nexperia', 'Chip-select bank OR gates', 'Quad 2-input OR, TSSOP-14; powered at 3.3 V'),
    '74LVC04AT14-13': ('Diodes Incorporated', 'Bank / shared-IRQ inverters', 'Hex NOT, TSSOP-14; powered at 3.3 V'),
}


def main():
    REVIEW.mkdir(exist_ok=True, parents=True)
    for name in ('componentlist.md.txt', 'componentlist.csv'):
        source = REPO / name
        backup = REVIEW / ('componentlist-before-update.' + ('csv' if name.endswith('.csv') else 'md.txt'))
        if source.exists() and not backup.exists():
            shutil.copy2(source, backup)

    parts = json.loads((ROOT / 'parts.json').read_text())
    updates = json.loads((ROOT / 'sourcing_updates.json').read_text())
    usage = active_selection({p['symbol'].split(':', 1)[1] for p in parts})
    audit = json.loads((REVIEW / 'audit_results.json').read_text())
    digest = hashlib.sha256(SCHEMATIC.read_bytes()).hexdigest()
    assert digest == audit['schematic_sha256'], 'Schematic changed; regenerate netlist/audit first'
    rows = []
    for part in parts:
        p = dict(part)
        p.update(updates.get(p['mpn'], {}))
        name = p['symbol'].split(':', 1)[1]
        assert p['quantity'] == usage[name]['quantity'], ('Stale CAD inventory', p['mpn'])
        refs = sorted(usage[name]['references'], key=ref_key)
        maker, function, specs = DETAILS[p['mpn']]
        filename = p['mpn'].replace('/', '_').replace(',', '_').replace(' ', '_') + '.pdf'
        if p['mpn'] == 'RC0603FR-07100KL':
            filename = 'RC0603FR-0710KL.pdf'  # Same saved YAGEO RC_L family sheet.
        datasheet = REPO / 'datasheets' / filename
        assert datasheet.is_file(), datasheet
        missing_fp = [ref for ref in refs if ref in audit['missing_footprints']]
        status = 'ADD TO SCHEMATIC' if not refs else 'FOOTPRINT UNASSIGNED' if missing_fp else 'PLACED'
        row = dict(mpn=p['mpn'], manufacturer=maker, quantity=p['quantity'],
                   schematic_quantity=len(refs), placed_references=';'.join(refs),
                   status=status, function=function, specifications=specs,
                   supplier_url=p['supplier_url'], observed_stock=p['observed_stock'],
                   unit_usd=p['unit_usd'], checked_date=p['checked_date'],
                   sourcing_note=p.get('sourcing_note', 'Earlier supplier snapshot retained; recheck before ordering.'),
                   alternate_supplier_evidence=p.get('alternate_supplier_evidence', ''),
                   symbol=p['symbol'], footprint=p['footprint'], step=p['step'],
                   datasheet='datasheets/' + filename)
        rows.append(row)

    assert len(rows) == 20
    placed_count = sum(r['schematic_quantity'] for r in rows)
    planned_count = sum(r['quantity'] for r in rows)
    testpoint_count = audit['component_count'] - placed_count
    issues = []
    if not audit['gate_power_correct']:
        issues.append('move U1/U2/U4/U5 pin 14 and their bypass supply connections from 5 V to 3.3 V')
    if not audit['input_fuses']:
        issues.append('restore the series 1 A fuse')
    if audit['missing_footprints']:
        issues.append(f"assign the {len(audit['missing_footprints'])} missing footprints")
    required_changes = '; '.join(issues)
    price_total = sum(r['quantity'] * r['unit_usd'] for r in rows)
    head = f'''# 2 x SPI to 8 x CAN - current nonisolated V1 component list

Updated 2026-10-18 against the saved `breakout/breakout.kicad_sch` (SHA-256 `{digest}`). This replaces the old isolated-design inventory. Common ground, regulated 5 V input, a local 3.3 V LDO, eight MCP251863 controllers and four logic packages are the current architecture.

**{len(rows)} purchased MPN types, {planned_count} components per board including the requested 1 A fuse.** The saved schematic currently contains {placed_count} of those components plus {testpoint_count} test-point features. The fuse is counted in planned quantities even when not yet placed. PCB test-point features and optional additions are listed separately below.

**Remaining schematic work:** {required_changes}. The latest saved revision correctly powers all four logic packages and their bypass capacitors from 3.3 V. See [the complete review](review/latest/schematic_review.txt) for the CAD/ERC and prototype checks. Updating this list did not change the schematic.

## Components for one board

Quantities count physical packages, not individual gate units. `Qty` includes the missing fuse; `In schematic` states the actual placed count. All source prices are USD single-unit snapshots, with their observation dates in the CSV. Supplier quantities are not reservations. Quantity breaks can reduce actual cost.

| Function | Exact manufacturer part / source | Qty | In schematic | References | Package / value |
|---|---|---:|---:|---|---|
'''
    lines = []
    for r in rows:
        refs = display_refs(r['placed_references'].split(';') if r['placed_references'] else [])
        lines.append(f"| {r['function']} | [{r['mpn']}]({r['supplier_url']}) | {r['quantity']} | {r['schematic_quantity']} | {refs} | {r['specifications']} |")
    pricing = '''

## Sourcing snapshots

The crystal, 1 uF capacitors, bulk-capacitor listing and 2-pin power connector were rechecked on 2026-10-18 to fill earlier missing prices. Other rows retain their recorded dates; they were not all re-quoted during this BOM update. Stock for the bulk capacitor needs particular attention: DigiKey's opened page shows zero, despite a stale indexed result showing stock.

| MPN | Stock snapshot | USD each, qty 1 | Checked |
|---|---:|---:|---|
'''
    for r in rows:
        pricing += f"| [{r['mpn']}]({r['supplier_url']}) | {r['observed_stock']:,} | ${r['unit_usd']:.2f} | {r['checked_date']} |\n"
    pricing += f'''
Multiplying the listed single-unit prices by the board quantities gives approximately **${price_total:.2f} per board** before tax, tariffs, shipping, PCB, assembly, mating connectors and cables. This arithmetic includes the out-of-stock DigiKey bulk-capacitor listing and is **not a stock-backed cart quotation**. Use quantity pricing for actual orders; for example, 27 pF capacitors were $0.028 each at quantity 10 and 10 kohm resistors $0.014 each at quantity 10 in the earlier snapshots.

**Bulk capacitor availability:** retain the selected Samsung CL21B106KOQNNNE (10 uF, 16 V, X7R, 0805). [DigiKey's direct listing](https://www.digikey.com/en/products/detail/samsung-electro-mechanics/CL21B106KOQNNNE/3890958) showed zero stock when opened. [Mouser's alternative-packaging listing](https://www.mouser.com/en/ProductDetail/Samsung-Electro-Mechanics/CL21B106KOQNNNG?qs=Wt8QXSv5fpijNSc%252BYtlvng%3D%3D) identified the exact E-suffix MPN as in stock; confirm the selected part and availability in the cart. No lower-voltage substitute has been selected automatically.
'''
    notes = '''

## Power and reverse-polarity wiring

- J6 pin 1 = common GND; J6 pin 2 = regulated +5 V input. These match the saved schematic. Check the physical connector orientation when making the cable.
- Add the requested 0466001.NR 1 A fuse between J6.2 and Q1.3. The saved schematic presently connects them directly.
- AO3401A Q1: pin 1 = gate, pin 2 = source, pin 3 = drain. Drain faces the fused input; source feeds protected +5 V (`VCC`). R38 pulls gate to common GND through 10 kohm.
- BZT52C6V8-13-F D2: pin 1 / cathode to Q1 source, pin 2 / anode to Q1 gate. It clamps VGS; it is not a supply-to-ground shunt diode or a 5 V rail overvoltage clamp.
- C20, 10 uF, belongs after Q1 on protected +5 V. U3 takes protected +5 V on IN/EN and generates 3.3 V (`VDD_VIO`). C18/C19 are local 1 uF input/output capacitors; retain effective capacitance above TI's 0.47 uF minimum after derating.
- Every MCP251863 VCC pin 25 uses protected 5 V. Controller VDD pin 14, transceiver VIO pin 1, all gate supplies and chip-select pull-ups use 3.3 V. The latest saved schematic correctly connects the four gate supplies and their bypass capacitors to 3.3 V.

The AOS AO3401A is specified at a maximum 60 milliohm RDS(on) with VGS=-4.5 V under its 25 C test conditions: approximately 60 mV / 60 mW at 1 A, increasing when hot. This simple self-biased PFET protects static reverse hookup; it does not guarantee reverse-current blocking from a charged output, control inrush or protect against positive overvoltage / a 48 V miswire. [AOS datasheet](https://www.aosmd.com/sites/default/files/res/datasheets/AO3401A.pdf), [TI reverse-protection explanation](https://www.ti.com/lit/an/slvae57/slvae57.pdf).

The requested 1 A fuse remains a prototype selection requiring load and temperature validation. Littelfuse's 25% continuous-current derating gives about 0.75 A at room temperature, with further temperature derating. An allowance of eight times (20 mA controller + 0.5 mA VIO + 70 mA dominant transceiver) is already 0.724 A before other loads; this is an allocation, not a measured traffic average. Keep CAN VCC above 4.5 V after cable, fuse, MOSFET and PCB losses. See [the protection note](review/mosfet_reverse_protection.txt).

## Logic, resistor and capacitor allocation

- Two 74LVC32APW,118 packages U1/U5 provide eight OR gates, one for each CAN nCS. One 74LVC04AT14-13 U2 provides four bank inversions, the IRQ inversion, and one spare inverter. One 74AHC30PW,118 U4 combines eight interrupts. All four packages run at 3.3 V, each with one local 100 nF capacitor. Selected gate delays suit MHz operation, subject to actual SPI setup/hold and interconnect checks in the review.
- The 28 x 100 nF capacitors comprise 24 for CAN VDD/VIO/VCC (three per chip) and four for the logic packages. Every bypass needs a short local power/ground loop.
- The 16 x 33 ohm resistors comprise eight CAN SDO source resistors and eight header-side SCK/MOSI/native-CS series resistors. Keep them near their signal drivers. They are for edge damping, not DC voltage translation.
- The 9 x 10 kohm resistors comprise eight CAN nCS pull-ups to 3.3 V and Q1 gate pull-down R38. The 4 x 100 kohm resistors R34-R37 pull up the four native Jetson CS signals. Their placement before the 33 ohm resistors is electrically acceptable.
- GPIO_7 / J1.32 and GPIO_11 / J1.31 need confirmed startup states. If adding weak board-side bank pull-downs, allow **two additional RC0603FR-07100KL** resistors; these are not currently placed and are not included in the base quantity of four. External pulls on the carrier's TXB0108-connected pins should exceed 50 kohm, and require checks against actual boot/pinmux behavior. [TI guidance](https://www.ti.com/lit/an/scea054a/scea054a.pdf).
- All eight crystals use two 27 pF C0G capacitors, 16 total. Crystal CL=18 pF is not the individual capacitor value: two 27 pF capacitors contribute 13.5 pF in series, reaching 18 pF with about 4.5 pF effective stray. Validate startup, frequency and drive on the PCB; tune if necessary. [Microchip board-design hints](https://ww1.microchip.com/downloads/aemDocuments/documents/APID/ApplicationNotes/ApplicationNotes/MCP251863-Application-Note-00004560A.pdf).

The verified select mapping is:

| Bank GPIO | Active native CS | Selected CAN on SPI0 | Selected CAN on SPI1 |
|---:|---|---:|---:|
| 0 | CS0 low | CAN2 | CAN6 |
| 0 | CS1 low | CAN3 | CAN7 |
| 1 | CS0 low | CAN1 | CAN5 |
| 1 | CS1 low | CAN4 | CAN8 |

Both native CS high deselect all devices. Never assert both native CS low on a bus. Change bank while both are high and allow the previous SDO to release. The NAND-plus-inverter IRQ is active LOW: configure a shared LEVEL_LOW interrupt and verify the installed JetPack driver/device-tree mux topology. Gates alone do not enumerate the four devices per SPI controller.

## Connectors, termination and test points

CAN connectors J4/J5/J7-J12: pin 1 = CANH, pin 2 = CANL, pin 3 = common GND. The eight 120 ohm resistors are permanently connected in this schematic, with no termination jumpers. This assumes each port is a bus endpoint with one other termination at the far end. Use exactly two terminations per CAN bus; introduce jumpers/DNP options if the topology requires them.

J1 is a male Harwin harness header, not an underside stacking socket. Its signal allocation follows the saved schematic's intended Jetson developer-carrier header mapping. Only J1.39 is currently grounded: connect the other available ground pins 6/9/14/20/25/30/34 for better signal return paths. Keep the local LDO output independent of Jetson 3.3 V. Mating XH housings/contacts, host cable and strain relief are outside this PCB component list; choose them for the actual wire gauge and harness arrangement.

The saved schematic has these additional PCB features, excluded from the 20 purchased MPN lines and price total:

| Feature | Qty | References | Status |
|---|---:|---|---|
| Single-net test point | 21 | TP1-TP12, TP15-TP23 | Footprint not assigned; choose bare pads or physical test points |
| Two-net test point | 2 | TP13-TP14 | Footprint/mechanics not assigned |

No separate test-point hardware MPN was selected. If these become fitted pin/loop components, add their purchased parts to the BOM. The 79 blank footprint fields consist of 19 capacitors, 37 resistors and these 23 test points. The retained C/R packages are listed below; they still need assignments in the schematic.

External CAN TVS parts are absent and excluded from this BOM. They are optional for basic signaling, but connector-side protection remains worth considering for the motor harness; see the review for context. They were not re-added during the requested unused-asset cleanup.

## Local CAD and datasheets

The pruned local library has 20 MPN symbols, 14 shared package footprints and 14 STEP models. `componentlist.csv` includes exact references, present/planned quantities, part status, package/model paths and local datasheet paths. The project's footprint-library table is now registered. STEP models are nominal official KiCad package geometry, not manufacturer-certified models of every individual MPN.

| MPN | Footprint in BreakoutBoard library | Saved datasheet |
|---|---|---|
'''
    assets = []
    for r in rows:
        assets.append(f"| {r['mpn']} | `{r['footprint']}` | [PDF]({r['datasheet']}) |")
    tail = '''

The 100 kohm resistor shares the saved YAGEO RC_L family datasheet with the 10 kohm resistor. The saved main MCP251863 PDF is Rev A; the newer Rev B reviewed for this schematic is at [review/MCP251863_RevB.pdf](review/MCP251863_RevB.pdf). The saved Zener family PDF is Diodes DS18004 Rev32-2; its newer manufacturer revision was checked online. The datasheet archive retains former-design documents for reference; their presence does not add those parts to this BOM.

The old isolators, isolated converter, eFuse and setting parts, unused AND gates, old reverse-protection diodes, old fuse/capacitor aliases and powered oscillator are removed from the active component list and CAD bundle. The old isolated design remains separately archived in `componentlist.isolated-reference-2026-10-17.md.txt` / `.csv`. The previous component list is in `review/latest/componentlist-before-update.md.txt` / `.csv`; the complete pre-cleanup CAD folder is in `review/latest/library-before-cleanup.zip`.

Rebuild this document with `python kicad_footprints/write_component_list.py` after regenerating the active library inventory and latest schematic audit. The generator checks the schematic hash and quantities rather than silently exporting stale counts.
'''
    TARGET.write_text(head + '\n'.join(lines) + pricing + notes + '\n'.join(assets) + tail, encoding='utf-8')
    with (REPO / 'componentlist.csv').open('w', newline='', encoding='utf-8-sig') as output:
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f'Updated componentlist.md.txt and componentlist.csv: {len(rows)} MPNs, {placed_count} placed parts, {planned_count} planned; unit-price arithmetic ${price_total:.2f}.')


if __name__ == '__main__':
    main()
