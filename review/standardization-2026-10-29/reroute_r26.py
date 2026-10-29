"""Align the 1206 pads with J10 and replace only the local bottom CAN stubs."""
from pathlib import Path
import json
import pcbnew as p
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
path=ROOT/'breakout/breakout.kicad_pcb'
b=p.LoadBoard(str(path))
f=next(x for x in b.GetFootprints() if x.GetReference()=='R26')
j=next(x for x in b.GetFootprints() if x.GetReference()=='J10')
assert f.GetOrientationDegrees()==0
f.SetOrientationDegrees(180)
f.GetField(p.FIELD_T_DESCRIPTION).SetText('Resistor')
pads={q.GetNumber():q for q in f.Pads()}
connectors={q.GetNumber():q for q in j.Pads()}
nets={pads['1'].GetNetname(),pads['2'].GetNetname()}
removed=[]
removed_items=[]
for t in list(b.GetTracks()):
    if t.GetNetname() in nets and t.GetLayer()==p.B_Cu:
        assert not isinstance(t,p.PCB_VIA)
        for v in (t.GetStart(),t.GetEnd()):
            assert 85.5<=p.ToMM(v.x)<=89 and 117.8<=p.ToMM(v.y)<=122.1
        removed.append(t.m_Uuid.AsString())
        b.Remove(t)
        removed_items.append(t)
assert len(removed)==10,removed
added=[]
for number,pad in pads.items():
    start=connectors[number].GetPosition()
    end=pad.GetPosition()
    delta=abs(end.x-start.x)
    bend=p.VECTOR2I(start.x,end.y+delta)
    for a,z in ((start,bend),(bend,end)):
        track=p.PCB_TRACK(b)
        track.SetStart(a);track.SetEnd(z);track.SetWidth(p.FromMM(.25))
        track.SetLayer(p.B_Cu);track.SetNet(pad.GetNet())
        b.Add(track);added.append(track.m_Uuid.AsString())
b.BuildConnectivity()
p.SaveBoard(str(path),b)
result={'orientation_degrees':180,'removed_local_track_uuids':removed,
 'added_local_track_uuids':added,'pad_positions_mm':{n:p.ToMM(q.GetPosition()) for n,q in pads.items()},
 'all_new_tracks_on':'B.Cu','new_track_width_mm':.25}
(OUT/'r26-routing.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
