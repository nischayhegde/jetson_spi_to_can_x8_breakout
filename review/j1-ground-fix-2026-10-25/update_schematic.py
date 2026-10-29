"""Connect only the seven previously-NC Jetson ground pins, preserving CAD text."""
from pathlib import Path
import hashlib, json, re, shutil, uuid
import sexpdata as sx
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
path=ROOT/'breakout/breakout.kicad_sch'
backup=OUT/'before.kicad_sch'
if backup.exists():raise RuntimeError('Backup already exists; do not repeat mutation')
raw=path.read_bytes()
text=raw.decode('utf-8')
newline='\r\n' if '\r\n' in text else '\n'
text=text.replace('\r\n','\n')
root=sx.loads(text)
def items(obj,kind):return [x for x in obj if isinstance(x,list) and x and str(x[0])==kind]
j=next(x for x in items(root,'symbol') if any(p[1:3]==['Reference','J1'] for p in items(x,'property')))
assert items(j,'at')[0][1:]==[60.96,99.06,0]
lib=items(root,'lib_symbols')[0]
sym=next(x for x in items(lib,'symbol') if x[1]==items(j,'lib_id')[0][1])
pinxy={int(items(p,'number')[0][1]):(round(60.96+items(p,'at')[0][1],2),round(99.06-items(p,'at')[0][2],2))
       for unit in items(sym,'symbol') for p in items(unit,'pin')}
pins=[6,9,14,20,25,30,34]
positions={pinxy[p]:p for p in pins}
removed=[]
def replace_nc(match):
    node=sx.loads(match.group(0).strip())
    at=tuple(items(node,'at')[0][1:])
    if at in positions:
        removed.append(positions[at]);return ''
    return match.group(0)
text=re.sub(r'^\t\(no_connect\n.*?^\t\)\n',replace_nc,text,flags=re.M|re.S)
assert sorted(removed)==pins,(removed,pins)
new=[]
for p in pins:
    x,y=pinxy[p]
    end=round(x+1.27,2) if p%2==0 else round(x-2.54,2)
    justify='left' if p%2==0 else 'right'
    new.append(f'''\t(wire
\t\t(pts
\t\t\t(xy {x:g} {y:g})
\t\t\t(xy {end:g} {y:g})
\t\t)
\t\t(stroke (width 0) (type default))
\t\t(uuid "{uuid.uuid4()}")
\t)
\t(label "GND"
\t\t(at {end:g} {y:g} 0)
\t\t(effects (font (size 1 1)) (justify {justify} bottom))
\t\t(uuid "{uuid.uuid4()}")
\t)
''')
insert=text.index('\t(symbol\n\t\t(lib_id ')
text=text[:insert]+''.join(new)+text[insert:]
sx.loads(text) # Validate syntax before writing.
shutil.copy2(path,backup)
path.write_bytes(text.replace('\n',newline).encode('utf-8'))
result={'added_ground_pins':pins,'existing_ground_pin':39,'schematic_pin_xy':{p:pinxy[p] for p in pins},
        'before_sha256':hashlib.sha256(raw).hexdigest(),'after_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
(OUT/'schematic_change.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
