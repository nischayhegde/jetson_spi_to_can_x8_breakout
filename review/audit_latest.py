"""Audit the saved schematic's KiCad XML export; never edits the design."""
from pathlib import Path
from collections import Counter
import csv
import hashlib
import itertools
import json
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'latest'
SCHEMATIC = ROOT.parent / 'breakout' / 'breakout.kicad_sch'
tree = ET.parse(OUT / 'breakout.net.xml').getroot()
components = {c.attrib['ref']: c for c in tree.findall('./components/comp')}
pin_net = {(n.attrib['ref'], n.attrib['pin']): net.attrib['name']
           for net in tree.findall('./nets/net') for n in net.findall('node')}


def net(ref, pin):
    return pin_net.get((ref, str(pin)), 'MISSING')


def value(ref):
    return components[ref].findtext('value')


def pair(ref):
    return {net(ref, 1), net(ref, 2)}


def series_destination(ref, pin, resistance='33'):
    source = net(ref, pin)
    found = []
    for name in components:
        if name.startswith('R') and value(name) == resistance and source in pair(name):
            found.append((name, next(iter(pair(name) - {source}), source)))
    return found


rows = []
for channel, number in enumerate(range(9, 17), 1):
    ref = f'U{number}'
    bus = 0 if channel <= 4 else 1
    crystal = f'Y{channel}'
    connector = f'J{[4,5,7,8,9,10,11,12][channel-1]}'
    termination = f'R{[6,10,13,16,23,26,29,32][channel-1]}'
    cap_numbers = [[1,2,3],[8,9,10],[11,12,13],[14,15,16],
                   [18,19,20],[21,22,23],[24,25,26],[27,28,29]][channel-1]
    cap_pairs = [pair(f'CC0603KRX7R9BB{n}') for n in cap_numbers]
    result = dict(channel=channel, reference=ref, expected_spi=bus,
                  VCC_pin25=net(ref,25), VDD_pin14=net(ref,14), VIO_pin1=net(ref,1),
                  SCK_pin9=net(ref,9), SDI_pin10=net(ref,10),
                  SDO_via_resistor=series_destination(ref,11),
                  CS_pin13=net(ref,13), INT_pin19=net(ref,19))
    result['checks'] = {
        'power': net(ref,25) == net('U3',1) == net('Q1',2)
                 and net(ref,14) == net(ref,1) == net('U3',5),
        'spi': net(ref,9) == f'SPI{bus}_SCK' and net(ref,10) == f'SPI{bus}_MOSI'
               and len(result['SDO_via_resistor']) == 1
               and result['SDO_via_resistor'][0][1] == f'SPI{bus}_MISO',
        'chip_select': net(ref,13) == f'CAN{channel}_CS',
        'interrupt': net(ref,19) == f'CAN{channel}_INT',
        'internal_can_links': net(ref,15) == net(ref,23) and net(ref,28) == net(ref,16),
        'grounds_and_standby': net(ref,22) == net(ref,24) == net(ref,5) == 'GND',
        'crystal': net(crystal,1) == net(ref,21) and net(crystal,3) == net(ref,20)
                   and net(crystal,2) == net(crystal,4) == 'GND',
        'crystal_capacitors': all(any(c.find('libsource').attrib == components[f'C{2*channel}'].find('libsource').attrib
                                    and c.findtext('value') == '27p'
                                    and pair(c.attrib['ref']) == {net(ref,pin),'GND'}
                                    for c in components.values() if c.attrib['ref'].startswith('C'))
                                 for pin in (20,21)),
        'local_bypass': cap_pairs.count({'GND',net('U3',1)}) == 1
                        and cap_pairs.count({'GND',net('U3',5)}) == 2,
        'can_connector': net(connector,1) == net(ref,4) and net(connector,2) == net(ref,3)
                         and net(connector,3) == 'GND',
        'termination': value(termination) == '120'
                       and pair(termination) == {net(ref,3),net(ref,4)},
    }
    rows.append(result)

gates = {}
for ref in ('U1','U5'):
    for a,b,y in ((1,2,3),(4,5,6),(9,10,8),(12,13,11)):
        gates[net(ref,y)] = ('OR',net(ref,a),net(ref,b))
for a,y in ((1,2),(3,4),(5,6),(9,8),(11,10),(13,12)):
    gates[net('U2',y)] = ('NOT',net('U2',a))
gates[net('U4',8)] = ('NAND',*(net('U4',p) for p in (1,2,3,4,5,6,11,12)))


def evaluate(name, signals):
    if name in signals:
        return signals[name]
    kind,*inputs = gates[name]
    values = [evaluate(n,signals) for n in inputs]
    return int(not values[0]) if kind == 'NOT' else int(not all(values)) if kind == 'NAND' else int(any(values))


bank_table = []
for bus,bank_name,first in ((0,'GPIO_7',1),(1,'GPIO_11',5)):
    for bank,cs0,cs1 in itertools.product((0,1),repeat=3):
        signals = {bank_name:bank,f'SPI{bus}_CS0':cs0,f'SPI{bus}_CS1':cs1}
        levels = {f'CAN{n}_CS':evaluate(f'CAN{n}_CS',signals) for n in range(first,first+4)}
        bank_table.append(dict(spi=bus,bank=bank,native_cs0=cs0,native_cs1=cs1,
                               forbidden_both_active=cs0==cs1==0,levels=levels,
                               selected=[name for name,v in levels.items() if not v]))
irq_table = []
for states in itertools.product((0,1),repeat=8):
    signals = {f'CAN{i}_INT':v for i,v in enumerate(states,1)}
    irq_table.append(dict(inputs=states,jetson_irq=evaluate('GPIO_1',signals)))

erc_path = OUT / 'erc_after.json'
if not erc_path.exists():
    erc_path = OUT / 'erc_before.json'
violations = [v for sheet in json.loads(erc_path.read_text())['sheets'] for v in sheet['violations']]
summary = dict(
    schematic_sha256=hashlib.sha256(SCHEMATIC.read_bytes()).hexdigest(),
    schematic_unchanged_since_snapshot=hashlib.sha256(SCHEMATIC.read_bytes()).hexdigest()
        == json.loads((OUT/'input_snapshot.json').read_text())['breakout/breakout.kicad_sch']['sha256'],
    component_count=len(components),
    channel_checks=rows,
    all_eight_channel_checks_pass=all(all(row['checks'].values()) for row in rows),
    gate_power={ref:net(ref,14) for ref in ('U1','U2','U4','U5')},
    gate_power_correct=all(net(ref,14)==net('U3',5) for ref in ('U1','U2','U4','U5')),
    gate_bypass_correct=all(pair(f'CC0603KRX7R9BB{n}')=={'GND',net('U3',5)}
                            for n in (5,6,7,17)),
    input_fuses=[ref for ref in components if ref.startswith('F')],
    protection_checks={
        'drain_to_input':net('Q1',3)==net('J6',2),
        'source_to_protected_rail':net('Q1',2)==net('U3',1),
        'zener_cathode_to_source':net('D2',1)==net('Q1',2),
        'zener_anode_to_gate':net('D2',2)==net('Q1',1),
        'gate_pulldown':value('R38')=='10k' and pair('R38')=={net('Q1',1),'GND'},
        'bulk_after_mosfet':value('C20')=='10u' and pair('C20')=={net('Q1',2),'GND'},
        'ldo_input_capacitor':value('C18')=='1u' and pair('C18')=={net('U3',1),'GND'},
        'ldo_output_capacitor':value('C19')=='1u' and pair('C19')=={net('U3',5),'GND'},
    },
    bank_idle_deselects_all=all(not row['selected'] for row in bank_table
                                if row['native_cs0']==row['native_cs1']==1),
    bank_single_select=all(len(row['selected'])==1 for row in bank_table
                           if row['native_cs0']!=row['native_cs1']),
    shared_irq_active_low=all(row['jetson_irq']==int(all(row['inputs'])) for row in irq_table),
    erc_file=erc_path.name,erc_total=len(violations),
    erc_severity_counts=dict(Counter(v['severity'] for v in violations)),
    erc_type_counts=dict(Counter(v['type'] for v in violations)),
    missing_footprints=[ref for ref,c in components.items() if not c.findtext('footprint')],
    header_connected_ground_pins=[p for p in (6,9,14,20,25,30,34,39) if net('J1',p)=='GND'],
)
(OUT/'audit_results.json').write_text(json.dumps(summary,indent=2)+'\n')
(OUT/'bank_truth_table.json').write_text(json.dumps(bank_table,indent=2)+'\n')
(OUT/'irq_truth_table.json').write_text(json.dumps(irq_table,indent=2)+'\n')
with (OUT/'channel_audit.csv').open('w',newline='') as output:
    data=[{**{k:v for k,v in r.items() if k!='checks'},**r['checks']} for r in rows]
    writer=csv.DictWriter(output,fieldnames=data[0]);writer.writeheader();writer.writerows(data)
print(json.dumps({k:v for k,v in summary.items() if k not in ('channel_checks','missing_footprints')},indent=2))
print('Missing footprints:',len(summary['missing_footprints']))
