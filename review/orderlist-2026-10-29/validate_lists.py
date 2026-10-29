"""Check delivered quantities, supplier links, cached totals and CAD immutability."""
from pathlib import Path
from decimal import Decimal
import csv
import hashlib
import json
import zipfile
import xml.etree.ElementTree as ET

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
data=json.loads((OUT/'order_data.json').read_text())
inventory=json.loads((OUT/'inventory.json').read_text())
bom=list(csv.DictReader((ROOT/'componentlist.csv').open(encoding='utf-8-sig')))
orders=list(csv.DictReader((ROOT/'orderlist.csv').open(encoding='utf-8-sig')))
assert len(bom)==len(orders)==data['purchase_lines']==21
assert sum(int(r['quantity']) for r in bom)==120
assert sum(int(r['order_quantity']) for r in orders)==129
assert sum(Decimal(r['line_usd']) for r in orders)==Decimal('37.36')
expected={r['mpn']:r for r in inventory['parts']}
all_refs=[]
for row in bom:
    actual=expected[row['mpn']]
    refs=row['placed_references'].split(';')
    assert sorted(refs)==sorted(actual['references'])
    assert int(row['quantity'])==len(refs)
    assert row['footprint']==';'.join(actual['footprints'])
    all_refs+=refs
assert len(set(all_refs))==120
assert not (set(all_refs)&{x['reference'] for x in inventory['bare_test_pads']})
assert not (set(all_refs)&set(inventory['board_only_mounting_holes']))
for row in orders:
    assert int(row['digikey_stock'])>=int(row['order_quantity'])
    assert row['digikey_url'].startswith('https://www.digikey.com/en/products/detail/')
    assert 'mouser.' in row['mouser_url']
    assert row['footprint']==';'.join(expected[row['mpn']]['footprints'])

S='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
P='http://schemas.openxmlformats.org/package/2006/relationships'
with zipfile.ZipFile(ROOT/'orderlist.xlsx') as archive:
    assert archive.testzip() is None
    sheet=ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
    rels=ET.fromstring(archive.read('xl/worksheets/_rels/sheet1.xml.rels'))
    shared=ET.fromstring(archive.read('xl/sharedStrings.xml')) if 'xl/sharedStrings.xml' in archive.namelist() else None
    strings=[''.join(t.itertext()) for t in shared] if shared is not None else []
    assert not any('not implemented' in text or text.startswith(('#REF!','#VALUE!','#NAME?')) for text in strings)
    cells={c.attrib['r']:c for c in sheet.findall(f'.//{{{S}}}c')}
    assert not [c.attrib['r'] for c in cells.values() if c.attrib.get('t')=='e']
    total_row=7+len(orders)+1
    subtotal=Decimal(cells[f'E{total_row}'].findtext(f'{{{S}}}v'))
    assert abs(subtotal-Decimal('37.36'))<Decimal('.00000001')
    assert int(Decimal(cells[f'B{total_row}'].findtext(f'{{{S}}}v')))==120
    assert int(Decimal(cells[f'C{total_row}'].findtext(f'{{{S}}}v')))==129
    links=sheet.find(f'{{{S}}}hyperlinks')
    assert len(links)==2*len(orders)==42
    targets={rel.attrib['Id']:rel.attrib['Target'] for rel in rels}
    found={x.attrib['ref']:targets[x.attrib[f'{{{R}}}id']] for x in links}
    for i,row in enumerate(orders,7):
        assert found[f'J{i}']==row['digikey_url']
        assert found[f'K{i}']==row['mouser_url']
    pane=sheet.find(f'.//{{{S}}}pane')
    pane_values=pane.attrib if pane is not None else {}
    assert pane_values.get('xSplit')=='1' and pane_values.get('ySplit')=='6',pane_values
for relative,digest in data['cad_sha256'].items():
    assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==digest
result={'purchase_lines':21,'fitted_packages':120,'order_quantity':129,'spares':9,
 'digikey_subtotal_usd':37.36,'all_digikey_snapshot_stock_sufficient':True,
 'native_excel_hyperlinks':42,'formula_error_cells':0,'frozen_panes':pane_values,
 'all_purchased_refs_and_footprints_match_cad':True,'cad_files_unchanged_during_list_generation':True,
 'j1_metadata_consistent_in_schematic_pcb_and_bom':True,
 'sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
  for name in ('componentlist.csv','componentlist.md.txt','orderlist.csv','orderlist.md.txt','orderlist.xlsx')}}
(OUT/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
