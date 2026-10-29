"""Join the CAD inventory and supplier observations into authoring inputs."""
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
import csv
import hashlib
import json
import shutil

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
inventory = json.loads((OUT/'inventory.json').read_text())
quotes = json.loads((OUT/'supplier_quotes.json').read_text())
for relative,digest in inventory['sha256'].items():
    assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==digest
for name in ('componentlist.csv','componentlist.md.txt'):
    backup=OUT/('before-'+name)
    if not backup.exists():
        shutil.copy2(ROOT/name,backup)
old={r['mpn']:r for r in csv.DictReader((OUT/'before-componentlist.csv').open(encoding='utf-8-sig'))}
evidence_urls={
 'CGA3E1X7R1E105K080AC':'https://www.mouser.com/en/c/passive-components/capacitors/ceramic-capacitors/mlccs-multilayer-ceramic-capacitors/?capacitance=1+uF&dielectric=X7R&product=Automotive+MLCCs&voltage+rating+dc=25+VDC',
 'RC1206FR-07120RL':'https://www.mouser.com/en/c/passive-components/resistors/smd-resistors-chip-resistors/?pg=5&q=120ohm+resistor&tolerance=0.1+%25%7C~0.5+%25%7C~1+%25%7C~2+%25',
 'RC0603FR-07100KL':'https://www.mouser.com/en/c/passive-components/resistors/smd-resistors-chip-resistors/thick-film-resistors/?case+code+-+in=0603&resistance=100+kOhms&tolerance=1+%25',
 'B2B-XH-A':'https://www.mouser.co.za/en/ProductDetail/JST-Commercial/B2B-XH-ALFSN?qs=cdbOS8ANM9DdcSn9qRmfCw%3D%3D',
 'M20-9990246':'https://www.mouser.co.il/en/ProductDetail/Harwin/M20-9990246?qs=sGAEpiMZZMvlX3nhDDO4AAIUUFD6r3d5GOgk8mOB0I8%3D',
 'CL21B106KOQNNNE':'https://www.mouser.co.il/en/ProductDetail/Samsung-Electro-Mechanics/CL21B106KOQNNNE?qs=349EhDEZ59r8qgLddyW2Yw%3D%3D',
}
actual={r['mpn']:r for r in inventory['parts']}
rows=[]
for quote in quotes['parts']:
    mpn=quote['mpn']
    if mpn not in actual:
        continue
    item=actual[mpn]
    prior=old.get(mpn,{})
    notes=[]
    if mpn=='M20-7832046':
        maker='Harwin'
        function='Jetson 40-pin female socket'
        spec='Female 2 x 20, 2.54 mm pitch, vertical through-hole; 8.5 mm above PCB; tin contacts'
        notes.append('J1 consistently uses M20-7832046 and the female socket footprint in the schematic, PCB and order list.')
    elif mpn=='M20-9990246':
        maker='Harwin'
        function='Two-pin test header'
        spec='Male 1 x 2, 2.54 mm pitch, vertical through-hole; 0.64 mm square pins; 3 mm solder tails'
        notes.append('Fitted headers for TP13 and TP14. The other 21 test points are bare PCB pads.')
    else:
        maker=prior['manufacturer']
        function=prior['function'].replace(' - ADD','')
        spec=prior['specifications'].replace('; see availability note','')
        if mpn=='0466001.NR':
            function='Series input fuse'
            spec='1 A, 63 V AC/DC, fast acting, 1206'
            notes.append('F1 is fitted in the current schematic and layout.')
        if mpn=='RC1206FR-07120RL':
            notes.append('All eight CAN termination resistors use this 1206, 120-ohm, 1%, 0.25 W part.')
        if mpn=='CC0603KRX7R9BB104':
            notes.append('28 x 100 nF bypass capacitors: C1 and C21-C47. MPN retained in hidden fields.')
        if mpn=='AO3401A':
            notes.append('Keep Alpha & Omega AO3401A. No alternate MOSFET selected.')
    required=item['quantity']
    dk=quote['digikey']
    assert dk['stock']>=required
    candidates=[]
    for quantity in {required}|{q for q,price in dk['price_breaks'] if required<=q<=max(25,required)}:
        price=Decimal(str(max((x for x in dk['price_breaks'] if x[0]<=quantity),key=lambda x:x[0])[1]))
        candidates.append((price*quantity,quantity,price))
    cost,order,price=min(candidates)
    if order>required:
        notes.append(f'Order {order} instead of {required}: the quantity discount lowers the line total.')
    mouser=quote['mouser']
    mp=max((x for x in mouser['price_breaks'] if x[0]<=order),key=lambda x:x[0])[1] if mouser['price_breaks'] else None
    # Supplier stock, price and provenance are independent facts.
    source_notes=' '.join(x for x in (mouser['notes'],dk['notes']) if x)
    rows.append(dict(mpn=mpn,manufacturer=maker,function=function,specifications=spec,
        quantity=required,order_quantity=order,spares=order-required,
        schematic_quantity=required,board_quantity=required,
        placed_references=';'.join(item['references']),design_value=';'.join(item['design_values']),
        footprint=';'.join(item['footprints']),status='PLACED',
        supplier_url=dk['url'],observed_stock=dk['stock'],unit_usd=float(price),
        line_usd=float(cost.quantize(Decimal('.01'),rounding=ROUND_HALF_UP)),
        checked_date=quotes['retrieved_date'],
        digikey_url=dk['url'],digikey_stock=dk['stock'],digikey_status=dk['status'],
        digikey_sku=dk['sku'],digikey_unit_usd=float(price),
        mouser_url=mouser['url'],mouser_stock=mouser['stock'],mouser_status=mouser['status'],
        mouser_unit_usd=mp,mouser_line_usd=round(mp*order+1e-8,2) if mp is not None else None,
        mouser_evidence_url=evidence_urls.get(mpn,mouser['url']),
        sourcing_note=source_notes,notes=' '.join(notes),
        datasheet=prior.get('datasheet',''),symbol=prior.get('symbol',''),
        unit_price_basis='DigiKey price break at order_quantity; cut tape or bulk/tube, no reeling fee'))

assert sum(r['quantity'] for r in rows)==120
assert sum(r['order_quantity'] for r in rows)==129
assert {r['mpn'] for r in rows}==set(actual)
summary=dict(date=quotes['retrieved_date'],currency='USD',boards=1,purchase_lines=len(rows),
    fitted_packages=120,order_quantity=129,spares=9,
    digikey_subtotal_usd=float(sum(Decimal(str(r['line_usd'])) for r in rows)),
    stock_basis=quotes['stock_basis'],cad_sha256=inventory['sha256'],
    cad_files_changed=True,rows=rows,pcb_features=inventory['bare_test_pads'],
    mounting_holes=inventory['board_only_mounting_holes'])
(OUT/'order_data.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ('rows','pcb_features','cad_sha256')},indent=2))
