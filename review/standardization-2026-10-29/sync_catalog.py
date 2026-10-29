"""Reconcile active library selections and test-header identity with the CAD BOM."""
from pathlib import Path
import copy,csv,hashlib,json,shutil
import sexpdata as sx

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
LIB=ROOT/'kicad_footprints/BreakoutBoard.kicad_sym'
SCH=ROOT/'breakout/breakout.kicad_sch'
S=sx.Symbol
def items(n,key):return [x for x in n if isinstance(x,list) and x and str(x[0])==key]
def field(n,key,value):
    found=next((x for x in items(n,'property') if x[1]==key),None)
    if found is not None:found[2]=value
    else:n.append([S('property'),key,value,[S('at'),0,0,0],[S('hide'),S('yes')],[S('effects'),[S('font'),[S('size'),1.27,1.27]]]])
def render(n,level=0):
    prefix='\t'*level
    if not isinstance(n,list):return prefix+sx.dumps(n)
    if not any(isinstance(x,list) for x in n):return prefix+sx.dumps(n)
    i=next(i for i,x in enumerate(n) if isinstance(x,list))
    return prefix+'('+' '.join(sx.dumps(x) for x in n[:i])+'\n'+'\n'.join(render(x,level+1) for x in n[i:])+'\n'+prefix+')'
def children(text):
    depth=0;quote=False;escape=False;start=0
    for i,c in enumerate(text):
        if escape:escape=False
        elif quote and c=='\\':escape=True
        elif c=='"':quote=not quote
        elif not quote:
            if c=='(':
                if depth==1:start=i
                depth+=1
            elif c==')':
                depth-=1
                if depth==1:yield text[start:i+1]
def pins(n):
    result=[]
    def visit(x):
        if not isinstance(x,list) or not x:return
        if str(x[0])=='pin':result.append(sx.dumps(x));return
        for child in x:visit(child)
    visit(n);return sorted(result)

text=SCH.read_text();sch=sx.loads(text);lib_text=LIB.read_text();lib=sx.loads(lib_text)
cache=items(sch,'lib_symbols')[0]
old=next(n for n in items(cache,'symbol') if n[1]=='Connector:TestPoint_2Pole')
new=copy.deepcopy(old);new[1]='M20-9990246'
def rename_units(n):
    for x in n:
        if isinstance(x,list):
            if x and str(x[0])=='symbol':x[1]=x[1].replace('TestPoint_2Pole','M20-9990246')
            rename_units(x)
rename_units(new)
for key,value in {'Reference':'TP','Value':'M20-9990246',
 'Footprint':'Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical',
 'MPN':'M20-9990246','Manufacturer':'Harwin','Datasheet':'https://www.harwin.com/products/M20-9990246'}.items():field(new,key,value)
assert pins(new)==pins(old)
assert not any(n[1]=='M20-9990246' for n in items(lib,'symbol'))
lib_text=lib_text.rstrip()[:-1]+render(new,1)+'\n)\n'
cached=copy.deepcopy(new);cached[1]='BreakoutBoard:M20-9990246'
cache[cache.index(old)]=cached
for n in items(sch,'symbol'):
    pr={x[1]:x[2] for x in items(n,'property')}
    if pr['Reference'] in ('TP13','TP14'):
        items(n,'lib_id')[0][1]='BreakoutBoard:M20-9990246'
        # Keep the existing purpose/description and pin geometry, changing only identity.
        field(n,'Datasheet','https://www.harwin.com/products/M20-9990246')
original=list(children(text));assert len(original)==len(sch)-1
cursor=0;result=''
for block,n in zip(original,sch[1:]):
    at=text.index(block,cursor)
    replacement=block if sx.loads(block)==n else render(n,1).lstrip('\t')
    result+=text[cursor:at]+replacement;cursor=at+len(block)
result+=text[cursor:]
sx.loads(result);sx.loads(lib_text)
LIB.write_text(lib_text,encoding='utf-8',newline='\n');SCH.write_text(result,encoding='utf-8',newline='\n')

old_parts=json.loads((OUT/'before/kicad_footprints/parts.json').read_text())
prior={r['mpn']:r for r in old_parts}
data=json.loads((ROOT/'review/orderlist-2026-10-29/order_data.json').read_text())
quotes={r['mpn']:r for r in json.loads((ROOT/'review/orderlist-2026-10-29/supplier_quotes.json').read_text())['parts']}
models=ROOT/'kicad_footprints/3dmodels'
for directory,name in [('Connector_PinSocket_2.54mm','PinSocket_2x20_P2.54mm_Vertical'),
 ('Connector_PinHeader_2.54mm','PinHeader_1x02_P2.54mm_Vertical')]:
    source=Path(r'C:/Program Files/KiCad/10.0/share/kicad/3dmodels')/(directory+'.3dshapes')/(name+'.step')
    assert source.is_file(),source
    shutil.copy2(source,models/source.name)
catalog=[]
for row in data['rows']:
    mpn=row['mpn']
    base=copy.deepcopy(prior.get(mpn,prior.get('M20-9982046') if mpn=='M20-7832046' else {}))
    if mpn=='M20-7832046':
        base.update(symbol='BreakoutBoard:M20-7832046',step='3dmodels/PinSocket_2x20_P2.54mm_Vertical.step',asset_origin='Connector_Generic:Conn_02x20_Odd_Even')
    if mpn=='M20-9990246':
        base.update(symbol='BreakoutBoard:M20-9990246',step='3dmodels/PinHeader_1x02_P2.54mm_Vertical.step',asset_origin='Connector:TestPoint_2Pole')
    base.update(mpn=mpn,manufacturer=row['manufacturer'],quantity=row['quantity'],function=row['function'],
      footprint=row['footprint'],supplier_url=row['digikey_url'],observed_stock=row['digikey_stock'],
      unit_usd=quotes[mpn]['digikey']['price_breaks'][0][1],checked_date=data['date'],
      placed_references=row['placed_references'],retention_reason='Explicit MPN field in saved schematic and PCB')
    catalog.append(base)
assert len(catalog)==21 and sum(r['quantity'] for r in catalog)==120
(ROOT/'kicad_footprints/parts.json').write_text(json.dumps(catalog,indent=2)+'\n')
headers=list(dict.fromkeys(k for row in catalog for k in row))
with (ROOT/'kicad_footprints/asset_manifest.csv').open('w',encoding='utf-8-sig',newline='') as target:
    writer=csv.DictWriter(target,fieldnames=headers);writer.writeheader();writer.writerows(catalog)
assets=[LIB]+list((ROOT/'kicad_footprints/BreakoutBoard.pretty').glob('*.kicad_mod'))+list(models.glob('*.step'))
hashes={str(p.relative_to(ROOT/'kicad_footprints')).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in assets}
(ROOT/'kicad_footprints/sha256.json').write_text(json.dumps(hashes,indent=2)+'\n')
print('Synchronized 21 active MPN selections and 120 packages; added exact test-header alias and matching socket/header 3D models.')
