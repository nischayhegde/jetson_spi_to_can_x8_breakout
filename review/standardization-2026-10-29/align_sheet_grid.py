"""Keep the rigid page translation on the original 1.27 mm connection grid."""
from pathlib import Path
import json,math,re
import sexpdata as sx
OUT=Path(__file__).resolve().parent
path=OUT.parents[1]/'breakout/breakout.kicad_sch'
change=json.loads((OUT/'schematic-change.json').read_text())
old=change['schematic_translation_mm']
new=[round(math.ceil(x/1.27)*1.27,6) for x in old]
delta=[round(b-a,6) for a,b in zip(old,new)]
assert any(delta)
text=path.read_text()
def update(m):
    block=m[0]
    def point(p):
        x=round(float(p[2])+delta[0],6);y=round(float(p[3])+delta[1],6)
        return f'({p[1]} {x:g} {y:g}'
    return re.sub(r'\((at|xy|start|end|center) (-?[\d.]+) (-?[\d.]+)',point,block)
kinds='symbol|wire|bus|junction|no_connect|label|global_label|hierarchical_label|text|text_box|polyline|rectangle|arc|circle|bus_entry|sheet|image'
text,count=re.subn(r'^\t\((?:'+kinds+r')(?: |\n).*?^\t\)\n',update,text,flags=re.M|re.S)
assert count>500,count
sx.loads(text)
path.write_text(text,encoding='utf-8',newline='\n')
change['schematic_translation_mm']=new
(OUT/'schematic-change.json').write_text(json.dumps(change,indent=2)+'\n')
print('Grid-aligned translation:',new,'updated root items:',count)
