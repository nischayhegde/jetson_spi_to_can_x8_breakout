"""Place compact global labels directly at header terminals, without open stubs."""
from pathlib import Path
import json, re, sexpdata as sx
OUT=Path(__file__).resolve().parent
path=OUT.parents[1]/'breakout/breakout.kicad_sch'
text=path.read_text(encoding='utf-8')
positions={int(p):xy for p,xy in json.loads((OUT/'schematic_change.json').read_text())['schematic_pin_xy'].items()}
root=sx.loads(text)
def it(a,k):return [x for x in a if isinstance(x,list) and x and str(x[0])==k]
removed=[]
def remove_wire(m):
    w=sx.loads(m[0].strip());pts=it(w,'pts')[0]
    coords=[list(x[1:]) for x in it(pts,'xy')]
    if len(coords)==2 and any(xy in coords for xy in positions.values()) and abs(coords[0][0]-coords[1][0]) in (1.269999999999996,2.539999999999999,1.27,2.54):
        removed.append(coords);return ''
    return m[0]
text=re.sub(r'^\t\(wire\n.*?^\t\)\n',remove_wire,text,flags=re.M|re.S)
assert len(removed)==7,removed
def place_label(m):
    node=sx.loads(m[0].strip());at=it(node,'at')[0]
    candidates=[(p,xy) for p,xy in positions.items() if abs(xy[1]-at[2])<.001]
    assert len(candidates)==1
    p,(x,y)=candidates[0];angle=0 if p%2==0 else 180
    block=re.sub(r'\(at [\d.]+ [\d.]+ [\d.]+\)',f'(at {x:g} {y:g} {angle})',m[0],count=1)
    block=re.sub(r'\(size [\d.]+ [\d.]+\)','(size 0.9 0.9)',block,count=1)
    return block.replace(' bottom)',' )').replace('left )','left)').replace('right )','right)')
text,count=re.subn(r'^\t\(global_label "GND"\n.*?^\t\)\n',place_label,text,flags=re.M|re.S)
assert count==7,count
sx.loads(text);path.write_text(text,encoding='utf-8',newline='\n')
print('Removed 7 open stubs; placed 7 compact global labels at header terminals')
