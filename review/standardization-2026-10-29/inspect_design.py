"""Snapshot the current design and inspect package/library consistency."""
from pathlib import Path
import hashlib,json,re,shutil
import sexpdata as sx

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
def items(node,key):
    return [x for x in node if isinstance(x,list) and x and str(x[0])==key]
def props(node):
    return {x[1]:x[2] for x in items(node,'property')}

files=['breakout/breakout.kicad_sch','breakout/breakout.kicad_pcb','breakout/breakout.kicad_pro',
 'kicad_footprints/BreakoutBoard.kicad_sym','kicad_footprints/parts.json',
 'kicad_footprints/asset_manifest.csv','kicad_footprints/sha256.json',
 'componentlist.csv','componentlist.md.txt','orderlist.csv','orderlist.md.txt','orderlist.xlsx']
snapshot={}
for relative in files:
    path=ROOT/relative
    backup=OUT/'before'/relative
    assert not backup.exists(),f'Do not repeat snapshot: {backup}'
    backup.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(path,backup)
    snapshot[relative]=hashlib.sha256(path.read_bytes()).hexdigest()
(OUT/'before-sha256.json').write_text(json.dumps(snapshot,indent=2)+'\n')
sch=sx.loads((ROOT/'breakout/breakout.kicad_sch').read_text())
library=sx.loads((ROOT/'kicad_footprints/BreakoutBoard.kicad_sym').read_text())
canonical={s[1]:s for s in items(library,'symbol')}
cached={s[1]:s for s in items(items(sch,'lib_symbols')[0],'symbol')}
references={}
for s in items(sch,'symbol'):
    pr=props(s)
    if pr['Reference'].startswith('#'):continue
    references.setdefault(pr['Reference'],[]).append({'lib_id':items(s,'lib_id')[0][1],
      'unit':items(s,'unit')[0][1],'properties':pr,'at':items(s,'at')[0][1:]})
diffs={}
for full,c in cached.items():
    if not full.startswith('BreakoutBoard:'):continue
    name=full.split(':',1)[1]
    expected=canonical.get(name)
    if expected is None:
        diffs[full]='Missing from library';continue
    a,b=props(c),props(expected)
    differences={k:[a.get(k),b.get(k)] for k in set(a)|set(b) if a.get(k)!=b.get(k)}
    if differences:diffs[full]=differences
result={'physical_refs':len(references),'placed_units':sum(map(len,references.values())),
 'library_property_differences':diffs,
 'termination_footprints':{r:references[r][0]['properties']['Footprint'] for r in ['R6','R10','R13','R16','R23','R26','R29','R32']},
 'j1':references['J1'],
 'nonstandard_refs':[r for r in references if not re.fullmatch(r'[A-Z]{1,3}\d+',r)],
 'references':references}
(OUT/'inspection.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='references'},indent=2))
