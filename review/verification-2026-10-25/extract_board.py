"""Read-only board geometry export. Run using KiCad's bundled Python."""
from pathlib import Path
from collections import Counter
import json
import pcbnew as p

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
b = p.LoadBoard(str(ROOT / 'breakout/breakout.kicad_pcb'))
def xy(v): return [p.ToMM(v.x), p.ToMM(v.y)]
def layers(item): return [b.GetLayerName(i) for i in item.GetLayerSet().Seq()]
data = {'version':p.Version(), 'footprints':{}, 'tracks':[], 'zones':[], 'drawings':[]}
for f in b.GetFootprints():
    data['footprints'][f.GetReference()] = {
        'value':f.GetValue(), 'library_id':f.GetFPID().GetLibItemName(),
        'at':xy(f.GetPosition()), 'orientation':f.GetOrientationDegrees(),
        'layer':b.GetLayerName(f.GetLayer()),
        'pads':[{'number':pad.GetNumber(), 'at':xy(pad.GetPosition()),
                 'orientation':pad.GetOrientationDegrees(),
                 'size':xy(pad.GetSize()), 'drill':xy(pad.GetDrillSize()),
                 'net':pad.GetNetname(), 'layers':layers(pad)} for pad in f.Pads()]}
for t in b.GetTracks():
    is_via = isinstance(t,p.PCB_VIA)
    data['tracks'].append({'type':'via' if is_via else 'track',
        'start':xy(t.GetStart()), 'end':xy(t.GetEnd()), 'width':p.ToMM(t.GetWidth(p.F_Cu) if is_via else t.GetWidth()),
        'length':p.ToMM(t.GetLength()), 'net':t.GetNetname(),
        'layers':layers(t), 'drill':p.ToMM(t.GetDrillValue()) if is_via else None})
for z in b.Zones():
    data['zones'].append({'net':z.GetNetname(), 'layers':layers(z),
                         'min_thickness':p.ToMM(z.GetMinThickness())})
for d in b.GetDrawings():
    row={'type':d.GetClass(),'layer':b.GetLayerName(d.GetLayer())}
    if hasattr(d,'GetStart'): row.update(start=xy(d.GetStart()), end=xy(d.GetEnd()))
    if hasattr(d,'GetText'): row['text']=d.GetText()
    data['drawings'].append(row)
(OUT/'board_geometry.json').write_text(json.dumps(data,indent=2,default=str))
print(json.dumps({'footprints':len(data['footprints']),
                  'track_counts':dict(Counter(t['type']+':'+','.join(t['layers']) for t in data['tracks'])),
                  'zones':data['zones']},default=str,indent=2))
