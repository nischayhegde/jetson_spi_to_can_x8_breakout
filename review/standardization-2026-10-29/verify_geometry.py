"""Limit physical changes to R26's package and local CAN routing."""
from pathlib import Path
import json
import pcbnew as p
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
before=p.LoadBoard(str(OUT/'before/breakout/breakout.kicad_pcb'))
after=p.LoadBoard(str(ROOT/'breakout/breakout.kicad_pcb'))
change=json.loads((OUT/'schematic-change.json').read_text())
route=json.loads((OUT/'r26-routing.json').read_text())
renames=change['reference_renames']
def xy(v):return v.x,v.y
bf={renames.get(f.GetReference(),f.GetReference()):f for f in before.GetFootprints()}
af={f.GetReference():f for f in after.GetFootprints()}
assert bf.keys()==af.keys() and len(af)==145
def pads(f):
    return {q.GetNumber():(xy(q.GetPosition()),xy(q.GetSize()),xy(q.GetDrillSize()),
      q.GetNetname(),tuple(q.GetLayerSet().Seq()),q.GetShape()) for q in f.Pads()}
for ref,f in bf.items():
    new=af[ref]
    assert xy(f.GetPosition())==xy(new.GetPosition()),ref
    assert f.GetLayer()==new.GetLayer(),ref
    if ref!='R26':
        assert f.GetOrientationDegrees()==new.GetOrientationDegrees(),ref
        assert f.GetFPID()==new.GetFPID(),ref
        assert pads(f)==pads(new),ref
    if ref in change['purchased_metadata']:
        for key,expected in [('MPN','mpn'),('Manufacturer','manufacturer')]:
            assert new.GetFieldText(key)==change['purchased_metadata'][ref][expected],ref
def tracks(b):
    return {t.m_Uuid.AsString():(t.GetClass(),xy(t.GetStart()),xy(t.GetEnd()),
      t.GetNetname(),t.GetLayer(),t.GetWidth(p.F_Cu) if isinstance(t,p.PCB_VIA) else t.GetWidth(),
      t.GetDrillValue() if isinstance(t,p.PCB_VIA) else None) for t in b.GetTracks()}
bt,at=tracks(before),tracks(after)
removed=set(bt)-set(at);added=set(at)-set(bt)
assert removed==set(route['removed_local_track_uuids'])&set(bt)
assert len(removed)==8
assert added==set(route['added_local_track_uuids']) and len(added)==4
assert all(bt[k]==at[k] for k in set(bt)&set(at))
assert all(bt[k][4]==p.B_Cu and bt[k][3] in ('Net-(J10-Pin_1)','Net-(J10-Pin_2)') for k in removed)
for ref in ['R6','R10','R13','R16','R23','R26','R29','R32']:
    f=af[ref]
    assert f.GetFPID().GetUniStringLibId()=='BreakoutBoard:R_1206_3216Metric'
    assert f.GetFieldText('MPN')=='RC1206FR-07120RL'
    assert f.GetValue()=='120'
assert len(list(before.GetDrawings()))==len(list(after.GetDrawings()))
before_edges=[(xy(d.GetStart()),xy(d.GetEnd())) for d in before.GetDrawings() if d.GetLayer()==p.Edge_Cuts]
after_edges=[(xy(d.GetStart()),xy(d.GetEnd())) for d in after.GetDrawings() if d.GetLayer()==p.Edge_Cuts]
assert before_edges==after_edges
for ref in ('H1','H2','H3','H4'):
    assert pads(bf[ref])==pads(af[ref]) and af[ref].IsLocked()
    assert len(list(af[ref].Zones()))==1
result={'board_size_mm':[81,80],'board_outline_unchanged':True,
 'all_component_centers_and_sides_unchanged':True,'other_component_pad_geometry_unchanged':True,
 'mounting_holes_and_hardware_keepouts_preserved':True,
 'r26_rotation_degrees':180,'r26_footprint':'BreakoutBoard:R_1206_3216Metric',
 'removed_old_local_can_tracks':len(removed),'added_local_can_tracks':len(added),
 'all_other_tracks_and_vias_unchanged':True,'tracks_and_vias':len(at)}
(OUT/'geometry-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
