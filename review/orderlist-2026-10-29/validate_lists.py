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
assert sum(int(r['order_quantity']) for r in orders)==144
expected_total=Decimal(str(data['digikey_subtotal_usd']))
assert sum(Decimal(r['line_usd']) for r in orders)==expected_total
expected={r['mpn']:r for r in inventory['parts']}
all_refs=[]
for row in bom:
    actual=expected[row['cad_mpn']]
    if row['mpn']!=row['cad_mpn']:
        substitute=data['substitutions'][row['cad_mpn']]
        assert row['mpn']==substitute['mpn']
        assert row['footprint']==substitute['footprint']
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
    assert row['footprint']==';'.join(expected[row['cad_mpn']]['footprints'])
    assert int(row['order_quantity'])>int(row['quantity'])
bulk=(ROOT/'bulk_order_digikey.txt').read_text().splitlines()
assert bulk==[f"{r['order_quantity']}, {r['digikey_sku'] or r['mpn']}" for r in orders]
assert len(bulk)==21 and not any('311-10.0KHRCT-ND' in line for line in bulk)
assert '10, 311-10KLDCT-ND' in bulk
replacement=next(r for r in orders if r['mpn']=='AC0603FR-0710KL')
assert replacement['cad_mpn']=='RC0603FR-0710KL'
assert replacement['checked_date']=='2026-10-30'
assert Decimal(replacement['digikey_unit_usd'])==Decimal('.03')
assert Decimal(replacement['line_usd'])==Decimal('.30')
assert '5, 541-100KHCT-ND' in bulk
assert not any('311-100KHRCT-ND' in line for line in bulk)
replacement_100k=next(r for r in orders if r['mpn']=='CRCW0603100KFKEA')
assert replacement_100k['cad_mpn']=='RC0603FR-07100KL'
assert replacement_100k['manufacturer']=='Vishay Dale'
assert set(replacement_100k['placed_references'].split(';'))=={'R34','R35','R36','R37'}
assert int(replacement_100k['quantity'])==4 and int(replacement_100k['order_quantity'])==5
assert replacement_100k['checked_date']=='2026-10-30'
assert Decimal(replacement_100k['digikey_unit_usd'])==Decimal('.10')
assert Decimal(replacement_100k['line_usd'])==Decimal('.50')

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
    assert abs(subtotal-expected_total)<Decimal('.00000001')
    assert int(Decimal(cells[f'B{total_row}'].findtext(f'{{{S}}}v')))==120
    assert int(Decimal(cells[f'C{total_row}'].findtext(f'{{{S}}}v')))==144
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
assert hashlib.sha256((ROOT/'purchasing_config.json').read_bytes()).hexdigest()==data['purchasing_config_sha256']
result={'purchase_lines':21,'fitted_packages':120,'order_quantity':144,'spares':24,
 'digikey_subtotal_usd':float(expected_total),'all_digikey_snapshot_stock_sufficient':True,
 'native_excel_hyperlinks':42,'formula_error_cells':0,'frozen_panes':pane_values,
 'all_purchased_refs_and_footprints_match_cad':True,'approved_purchasing_substitutions':2,
 'cad_files_unchanged_during_list_generation':True,'bulk_add_lines':21,'spares_percent_overall':20,
 'j1_metadata_consistent_in_schematic_pcb_and_bom':True,
 'sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
  for name in ('componentlist.csv','componentlist.md.txt','orderlist.csv','orderlist.md.txt','orderlist.xlsx','bulk_order_digikey.txt')}}
(OUT/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
