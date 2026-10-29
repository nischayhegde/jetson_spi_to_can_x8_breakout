"""Use global GND labels consistently and keep adjacent reference text legible."""
from pathlib import Path
import re, sexpdata as sx
OUT=Path(__file__).resolve().parent
path=OUT.parents[1]/'breakout/breakout.kicad_sch'
text=path.read_text(encoding='utf-8')
def convert(match):
    node=sx.loads(match.group(0).strip())
    at=next(x for x in node if isinstance(x,list) and str(x[0])=='at')
    angle='180' if at[1]<60 else '0'
    result=match.group(0).replace('(label "GND"','(global_label "GND"\n\t\t(shape input)',1)
    result=re.sub(r'(\(at [\d.]+ [\d.]+) 0\)',rf'\1 {angle})',result,count=1)
    return result
text,count=re.subn(r'^\t\(label "GND"\n.*?^\t\)\n',convert,text,flags=re.M|re.S)
assert count==7,count
# Move only the reference field of R21 away from the new pin-9 label.
pattern=r'(\(property "Reference" "R21"\s*\(at )([\d.]+)( [\d.]+ [\d.]+\))'
text,count=re.subn(pattern,lambda m:m[1]+f'{float(m[2])-2.54:g}'+m[3],text,count=1)
assert count==1
sx.loads(text)
path.write_text(text,encoding='utf-8',newline='\n')
print('Seven global GND labels; R21 reference field shifted for clearance')
