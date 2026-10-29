"""Standardize package metadata, references and symbol cache without rewiring."""
from pathlib import Path
import copy,csv,json,re,math
import sexpdata as sx

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
SCH=ROOT/'breakout/breakout.kicad_sch'
LIB=ROOT/'kicad_footprints/BreakoutBoard.kicad_sym'
assert SCH.read_bytes()==(OUT/'before/breakout/breakout.kicad_sch').read_bytes()
assert LIB.read_bytes()==(OUT/'before/kicad_footprints/BreakoutBoard.kicad_sym').read_bytes()
S=sx.Symbol
def items(n,key):return [x for x in n if isinstance(x,list) and x and str(x[0])==key]
def prop(n,key):return next((x for x in items(n,'property') if x[1]==key),None)
def props(n):return {x[1]:x[2] for x in items(n,'property')}
def field(n,key,value):
    target=prop(n,key)
    if target is not None:target[2]=value;return
    at=items(n,'at')
    x,y=at[0][1:3] if at else (0,0)
    n.append([S('property'),key,value,[S('at'),x,y,0],[S('hide'),S('yes')],
        [S('effects'),[S('font'),[S('size'),1.27,1.27]]]])
def children(text):
    depth=0;quoted=False;escaped=False;start=0
    for i,c in enumerate(text):
        if escaped:escaped=False
        elif quoted and c=='\\':escaped=True
        elif c=='"':quoted=not quoted
        elif not quoted:
            if c=='(':
                if depth==1:start=i
                depth+=1
            elif c==')':
                depth-=1
                if depth==1:yield text[start:i+1]
    assert depth==0 and not quoted
def render(n,level=0):
    indent='\t'*level
    if not isinstance(n,list):return indent+sx.dumps(n)
    if not any(isinstance(x,list) for x in n):return indent+sx.dumps(n)
    split=next(i for i,x in enumerate(n) if isinstance(x,list))
    return indent+'('+' '.join(sx.dumps(x) for x in n[:split])+'\n'+\
        '\n'.join(render(x,level+1) for x in n[split:])+'\n'+indent+')'
def pin_signature(n):
    found=[]
    def visit(x):
        if not isinstance(x,list) or not x:return
        if str(x[0])=='pin':found.append(sx.dumps(x));return
        for child in x:visit(child)
    visit(n)
    return sorted(found)

sch_text=SCH.read_text();root=sx.loads(sch_text)
lib_text=LIB.read_text();library=sx.loads(lib_text)
canonical={n[1]:n for n in items(library,'symbol')}
cached_container=items(root,'lib_symbols')[0]
cached={n[1]:n for n in items(cached_container,'symbol')}
bom=list(csv.DictReader((ROOT/'componentlist.csv').open(encoding='utf-8-sig')))
by_ref={r:row for row in bom for r in row['placed_references'].split(';')}
assert len(by_ref)==120
old_caps=sorted((r for r in by_ref if r.startswith('CC0603KRX7R9BB')),key=lambda r:int(r.rsplit('BB',1)[1]))
assert len(old_caps)==28
renames=dict(zip(old_caps,['C1']+[f'C{i}' for i in range(21,48)]))
metadata={}
for ref,row in by_ref.items():
    metadata[renames.get(ref,ref)]={'mpn':'RC1206FR-07120RL' if ref=='R26' else row['mpn'],
                                 'manufacturer':row['manufacturer']}

# Replace the stale male-header identity with the existing socket's exact part.
old_j=canonical['M20-9982046'];new_j=copy.deepcopy(old_j)
def rename_symbol(n,old,new):
    for x in n:
        if isinstance(x,list):
            if x and str(x[0])=='symbol' and isinstance(x[1],str):x[1]=x[1].replace(old,new)
            rename_symbol(x,old,new)
new_j[1]='M20-7832046';rename_symbol(new_j,'M20-9982046','M20-7832046')
for key,value in {'Value':'M20-7832046','Footprint':'Connector_PinSocket_2.54mm:PinSocket_2x20_P2.54mm_Vertical',
 'Datasheet':'https://www.harwin.com/products/M20-7832046',
 'Description':'40-pin female socket, 2 x 20, 2.54 mm pitch, vertical through-hole',
 'MPN':'M20-7832046','Manufacturer':'Harwin'}.items():field(new_j,key,value)
assert pin_signature(old_j)==pin_signature(new_j)
cap=copy.deepcopy(canonical['CC0603KRX7R9BB104'])
field(cap,'Value','100n');field(cap,'MPN','CC0603KRX7R9BB104');field(cap,'Manufacturer','YAGEO')
assert pin_signature(cap)==pin_signature(canonical['CC0603KRX7R9BB104'])
assert pin_signature(cap)==pin_signature(cached['BreakoutBoard:CC0603KRX7R9BB104'])

for old,new in [(old_j,new_j),(canonical['CC0603KRX7R9BB104'],cap)]:
    old_block=next(t for t in children(lib_text) if sx.loads(t)[:2]==old[:2])
    lib_text=lib_text.replace(old_block,render(new,1).lstrip('\t'),1)
for old_name,new in [('BreakoutBoard:M20-9982046',new_j),('BreakoutBoard:CC0603KRX7R9BB104',cap)]:
    old=cached[old_name]
    replacement=copy.deepcopy(new)
    replacement[1]='BreakoutBoard:'+replacement[1]
    assert pin_signature(old)==pin_signature(replacement)
    cached_container[cached_container.index(old)]=replacement

for n in items(root,'symbol'):
    pr=props(n);old_ref=pr['Reference'];ref=renames.get(old_ref,old_ref)
    if old_ref in renames:
        field(n,'Reference',ref);field(n,'Value','100n')
        def update_instances(x):
            if not isinstance(x,list):return
            if x and str(x[0])=='reference' and x[1]==old_ref:x[1]=ref
            for y in x:update_instances(y)
        update_instances(n)
    if ref=='R26':field(n,'Footprint','BreakoutBoard:R_1206_3216Metric')
    if ref=='J1':
        items(n,'lib_id')[0][1]='BreakoutBoard:M20-7832046'
        for key in ('Value','Footprint','Datasheet','Description'):field(n,key,props(new_j)[key])
    if ref in ('TP13','TP14'):field(n,'Value','M20-9990246')
    if ref in metadata:
        field(n,'MPN',metadata[ref]['mpn']);field(n,'Manufacturer',metadata[ref]['manufacturer'])

# Fit the entire drawing on a standard sheet using one rigid translation.
# Embedded symbol definitions stay in their local coordinate system.
geometry_kinds={'symbol','wire','bus','junction','no_connect','label','global_label','hierarchical_label',
 'text','text_box','polyline','rectangle','arc','circle','bus_entry','sheet','image'}
points=[]
def coordinates(n,offset=None):
    if not isinstance(n,list) or not n:return
    if offset is None and str(n[0])=='property' and any(str(x[1])=='yes' for x in items(n,'hide')):return
    if len(n)>2 and str(n[0]) in ('at','xy','start','end','center') and all(isinstance(v,(int,float)) for v in n[1:3]):
        if offset:
            n[1]=round(n[1]+offset[0],6);n[2]=round(n[2]+offset[1],6)
        else:points.append((n[1],n[2]))
        return
    for x in n:coordinates(x,offset)
geometry=[n for n in root if isinstance(n,list) and n and str(n[0]) in geometry_kinds]
for n in geometry:coordinates(n)
xmin,ymin=min(x for x,y in points),min(y for x,y in points)
dx,dy=[round(math.ceil(max(0,target-low)/1.27)*1.27,6) for target,low in [(30,xmin),(20,ymin)]]
xmax,ymax=max(x for x,y in points)+dx,max(y for x,y in points)+dy
assert xmax+45<841 and ymax+30<594,(xmin,ymin,xmax,ymax)
for n in geometry:coordinates(n,(dx,dy))
items(root,'paper')[0][1]='A1'

# Preserve text for untouched top-level blocks; serialize only modified blocks.
original_blocks=list(children(sch_text))
assert len(original_blocks)==len(root)-1
new_blocks=[]
for old_block,n in zip(original_blocks,root[1:]):
    new_blocks.append(old_block if sx.loads(old_block)==n else render(n,1).lstrip('\t'))
cursor=0;result=''
for block,new in zip(original_blocks,new_blocks):
    at=sch_text.index(block,cursor);result+=sch_text[cursor:at]+new;cursor=at+len(block)
result+=sch_text[cursor:]
sx.loads(result);sx.loads(lib_text)
LIB.write_text(lib_text,encoding='utf-8',newline='\n')
SCH.write_text(result,encoding='utf-8',newline='\n')
change={'reference_renames':renames,'purchased_metadata':metadata,
 'termination_mpn':'RC1206FR-07120RL','termination_footprint':'BreakoutBoard:R_1206_3216Metric',
 'j1_mpn':'M20-7832046','test_header_mpn':'M20-9990246',
 'schematic_translation_mm':[dx,dy],'paper':'A1','symbol_pin_definitions_unchanged':True}
(OUT/'schematic-change.json').write_text(json.dumps(change,indent=2)+'\n')
print(json.dumps({k:v for k,v in change.items() if k!='purchased_metadata'},indent=2))
