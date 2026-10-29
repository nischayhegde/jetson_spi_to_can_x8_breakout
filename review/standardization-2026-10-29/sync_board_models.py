"""Use project-local models for standard-library packages and match header metadata."""
from pathlib import Path
import json
import pcbnew as p
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
path=ROOT/'breakout/breakout.kicad_pcb'
b=p.LoadBoard(str(path));changes=[]
for f in b.GetFootprints():
    if f.GetReference() in ('TP13','TP14'):
        f.GetField(p.FIELD_T_DATASHEET).SetText('https://www.harwin.com/products/M20-9990246')
    for model in f.Models():
        filename=model.m_Filename
        if '${KICAD' not in filename:continue
        basename=Path(filename.replace('\\','/')).name
        basename=Path(basename).with_suffix('.step').name
        local=ROOT/'kicad_footprints/3dmodels'/basename
        assert local.is_file(),(f.GetReference(),filename,local)
        target='${KIPRJMOD}/../kicad_footprints/3dmodels/'+basename
        model.m_Filename=target
        changes.append({'reference':f.GetReference(),'before':filename,'after':target})
p.SaveBoard(str(path),b)
(OUT/'model-path-changes.json').write_text(json.dumps(changes,indent=2)+'\n')
print('Updated',len(changes),'model paths without changing pads or routing.')
