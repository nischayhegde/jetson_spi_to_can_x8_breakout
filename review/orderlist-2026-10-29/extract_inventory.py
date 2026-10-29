"""Reconcile physical schematic packages with the saved PCB, without CAD edits."""
from pathlib import Path
from collections import defaultdict
import csv
import hashlib
import json
import re
import xml.etree.ElementTree as ET
import pcbnew as p

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
pcb_path = ROOT/'breakout/breakout.kicad_pcb'
sch_path = ROOT/'breakout/breakout.kicad_sch'
b = p.LoadBoard(str(pcb_path))
fps = {f.GetReference():f for f in b.GetFootprints()}
components = ET.parse(OUT/'schematic.net.xml').findall('./components/comp')
groups = defaultdict(list)
features = []
for comp in components:
    ref = comp.attrib['ref']
    value = comp.findtext('value')
    footprint = comp.findtext('footprint')
    f = fps[ref]
    assert not f.IsDNP(), ref
    assert f.GetValue() == value, (ref,value,f.GetValue())
    assert f.GetFPID().GetUniStringLibId() == footprint, ref
    if footprint == 'TestPoint:TestPoint_Pad_D1.5mm':
        features.append({'reference':ref,'type':'Bare 1.5 mm test pad','footprint':footprint})
        continue
    mpn = comp.findtext("./fields/field[@name='MPN']")
    assert mpn, f'Missing explicit MPN on {ref}'
    assert f.GetFieldText('MPN') == mpn, f'Schematic/PCB MPN mismatch: {ref}'
    manufacturer = comp.findtext("./fields/field[@name='Manufacturer']")
    assert manufacturer and f.GetFieldText('Manufacturer') == manufacturer, ref
    groups[mpn].append({'reference':ref,'design_value':value,'footprint':footprint,
                        'pad_count':len(list(f.Pads())), 'side':b.GetLayerName(f.GetLayer())})

def key(ref):
    m = re.fullmatch(r'(.*?)(\d+)',ref)
    return m[1],int(m[2])

rows=[]
for mpn,items in groups.items():
    rows.append({'mpn':mpn, 'quantity':len(items),
        'references':sorted((x['reference'] for x in items),key=key),
        'design_values':sorted(set(x['design_value'] for x in items)),
        'footprints':sorted(set(x['footprint'] for x in items)), 'instances':items})
board_only = set(fps)-{c.attrib['ref'] for c in components}
assert board_only == {'H1','H2','H3','H4'}
assert len(features)==21 and len(rows)==21
assert sum(r['quantity'] for r in rows)==120
assert len(fps)==145 and len(components)==141
snapshot={'date':'2026-10-29','boards':1,'purchased_packages_per_board':120,
 'purchase_lines':len(rows),'schematic_physical_components':141,'pcb_footprints':145,
 'bare_test_pads':features,'board_only_mounting_holes':sorted(board_only),
 'sha256':{str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
           for path in (sch_path,pcb_path)},'parts':rows}
(OUT/'inventory.json').write_text(json.dumps(snapshot,indent=2)+'\n')
for row in rows:
    print(row['mpn'],row['quantity'],','.join(row['references']),','.join(row['footprints']))
print('120 purchased packages, 21 bare test pads, 4 non-purchased mounting holes.')
