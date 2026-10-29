"""Prove circuit equivalence and repeat the eight-channel logic/power checks."""
from pathlib import Path
from collections import Counter,defaultdict
import hashlib,json,xml.etree.ElementTree as ET

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
change=json.loads((OUT/'schematic-change.json').read_text())
renames=change['reference_renames']
before=ET.parse(OUT/'before.net.xml').getroot()
after=ET.parse(OUT/'after.net.xml').getroot()
def partition(tree,rename):
    return {frozenset((rename.get(n.attrib['ref'],n.attrib['ref']),n.attrib['pin'])
        for n in net.findall('node')) for net in tree.findall('./nets/net')}
assert partition(before,renames)==partition(after,{})
assert len(before.findall('./components/comp'))==len(after.findall('./components/comp'))==141
bc={renames.get(c.attrib['ref'],c.attrib['ref']):c for c in before.findall('./components/comp')}
ac={c.attrib['ref']:c for c in after.findall('./components/comp')}
assert bc.keys()==ac.keys()
for ref,c in bc.items():
    old_value=c.findtext('value');new_value=ac[ref].findtext('value')
    if ref in renames.values():assert new_value=='100n'
    elif ref=='J1':assert old_value=='M20-9982046' and new_value=='M20-7832046'
    elif ref in ('TP13','TP14'):assert new_value=='M20-9990246'
    else:assert old_value==new_value,(ref,old_value,new_value)
    assert set(c.findtext('tstamps').split())==set(ac[ref].findtext('tstamps').split()),ref

# Run the existing channel and exhaustive truth-table checks against the new
# references. The aliases below change lookup names only, not expected wiring.
code=(ROOT/'review/audit_latest.py').read_text().split("erc_path = OUT / 'erc_after.json'")[0]
code=code.replace('ROOT = Path(__file__).resolve().parent','ROOT = Path(__file__).resolve().parents[1]')
code=code.replace("OUT = ROOT / 'latest'","OUT = Path(__file__).resolve().parent")
code=code.replace("OUT / 'breakout.net.xml'","OUT / 'after.net.xml'")
code=code.replace("pin_net.get((ref, str(pin))","pin_net.get((renames.get(ref,ref), str(pin))")
exec(compile(code,'current_channel_audit','exec'))
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
assert all(all(row['checks'].values()) for row in rows)
assert all(net(r,14)==net('U3',5) for r in ('U1','U2','U4','U5'))
assert all(pair(f'CC0603KRX7R9BB{n}')=={'GND',net('U3',5)} for n in (5,6,7,17))
assert all(not r['selected'] for r in bank_table if r['native_cs0']==r['native_cs1']==1)
assert all(len(r['selected'])==1 for r in bank_table if r['native_cs0']!=r['native_cs1'])
assert all(r['jetson_irq']==int(all(r['inputs'])) for r in irq_table)
assert net('J6',1)=='GND' and net('J6',2) in pair('F1')
assert pair('F1')=={net('J6',2),net('Q1',3)}
assert net('Q1',2)==net('U3',1)==net('D2',1)
assert net('Q1',1)==net('D2',2)
assert pair('R38')=={net('Q1',1),'GND'}
assert all(net('J1',i)=='GND' for i in (6,9,14,20,25,30,34,39))
assert all(net('J1',i)!=net('U3',5) for i in (1,17))
assert not [r for r,c in components.items() if not c.findtext('footprint')]
mpns=defaultdict(list)
for ref,c in components.items():
    field=c.find("./fields/field[@name='MPN']")
    if field is not None:mpns[field.text].append(ref)
assert len(mpns)==21 and sum(map(len,mpns.values()))==120
assert set(mpns['RC1206FR-07120RL'])=={'R6','R10','R13','R16','R23','R26','R29','R32'}
assert not any('RC0603FR-07120RL'==m for m in mpns)
assert mpns['M20-7832046']==['J1']
assert set(mpns['M20-9990246'])=={'TP13','TP14'}
assert set(r for r in components if r.startswith('C') and r[1:].isdigit())=={f'C{i}' for i in range(1,48)}
erc=json.loads((OUT/'erc-after.json').read_text())
ev=[v for s in erc['sheets'] for v in s['violations']]
assert not ev,Counter(x['type'] for x in ev)
drc=json.loads((OUT/'drc-after.json').read_text())
assert all(not drc[k] for k in ('violations','unconnected_items','schematic_parity'))
baseline=json.loads((OUT/'before-sha256.json').read_text())
assert hashlib.sha256((ROOT/'breakout/breakout.kicad_pro').read_bytes()).hexdigest()==baseline['breakout/breakout.kicad_pro']
result={'net_partition_unchanged':True,'physical_schematic_components':141,
 'purchased_packages':120,'purchased_mpn_types':21,'all_eight_channel_checks_pass':True,
 'bank_truth_table_rows':len(bank_table),'irq_truth_table_rows':len(irq_table),
 'power_ground_and_input_protection_checks_pass':True,
 'termination_references':sorted(mpns['RC1206FR-07120RL']),
 'erc_violations':0,'drc_violations':0,'unconnected_items':0,'schematic_parity_issues':0,
 'project_rules_and_exclusions_unchanged':True,
 'mpn_references':dict(mpns),'channel_checks':rows}
(OUT/'electrical-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('mpn_references','channel_checks')},indent=2))
