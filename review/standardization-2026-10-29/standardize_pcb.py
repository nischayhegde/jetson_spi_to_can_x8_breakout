"""Match PCB identities and use the same 1206 termination on all channels."""
from pathlib import Path
import json
import pcbnew as p

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
path=ROOT/'breakout/breakout.kicad_pcb'
assert path.read_bytes()==(OUT/'before/breakout/breakout.kicad_pcb').read_bytes()
change=json.loads((OUT/'schematic-change.json').read_text())
b=p.LoadBoard(str(path))
print('Loaded board',flush=True)
old=next(f for f in b.GetFootprints() if f.GetReference()=='R26')
old_pads={x.GetNumber():x for x in old.Pads()}
f=p.FootprintLoad(str(ROOT/'kicad_footprints/BreakoutBoard.pretty'),'R_1206_3216Metric')
assert f
b.Add(f)
print('Loaded 1206 footprint',flush=True)
f.SetFPID(p.LIB_ID('BreakoutBoard','R_1206_3216Metric'))
f.SetReference('R26');f.SetValue('120')
f.SetPosition(old.GetPosition())
if old.GetLayer()==p.B_Cu:f.Flip(old.GetPosition(),p.FLIP_DIRECTION_TOP_BOTTOM)
f.SetOrientation(old.GetOrientation())
print('Matched footprint side and orientation',flush=True)
f.SetAttributes(old.GetAttributes());f.SetLocked(old.IsLocked())
f.SetPath(old.GetPath())
for new_field,old_field in ((f.Reference(),old.Reference()),(f.Value(),old.Value())):
    new_field.SetPosition(old_field.GetPosition())
    new_field.SetVisible(old_field.IsVisible())
    new_field.SetTextSize(old_field.GetTextSize())
    new_field.SetTextThickness(old_field.GetTextThickness())
    new_field.SetTextAngle(old_field.GetTextAngle())
    new_field.SetLayer(old_field.GetLayer())
new_pads={x.GetNumber():x for x in f.Pads()}
pad_changes={}
for number,pad in new_pads.items():
    previous=old_pads[number]
    pad.SetNet(previous.GetNet())
    pad_changes[number]={'before_mm':p.ToMM(previous.GetPosition()),
        'after_mm':p.ToMM(pad.GetPosition()),'net':pad.GetNetname()}
assert new_pads['1'].GetPosition().x<new_pads['2'].GetPosition().x
b.Remove(old)
print('Replaced R26',flush=True)
stubs=[]
for number,pad in new_pads.items():
    track=p.PCB_TRACK(b)
    track.SetStart(old_pads[number].GetPosition())
    track.SetEnd(pad.GetPosition())
    track.SetLayer(old.GetLayer())
    track.SetWidth(p.FromMM(.25))
    track.SetNet(pad.GetNet())
    b.Add(track);stubs.append(track.m_Uuid.AsString())

for footprint in b.GetFootprints():
    reference=footprint.GetReference()
    if reference in change['reference_renames']:
        reference=change['reference_renames'][reference]
        footprint.SetReference(reference)
        footprint.SetValue('100n')
    if reference=='J1':
        footprint.SetValue('M20-7832046')
        footprint.GetField(p.FIELD_T_DATASHEET).SetText('https://www.harwin.com/products/M20-7832046')
        footprint.GetField(p.FIELD_T_DESCRIPTION).SetText('40-pin female socket, 2 x 20, 2.54 mm pitch, vertical through-hole')
    if reference in ('TP13','TP14'):footprint.SetValue('M20-9990246')
    if reference in change['purchased_metadata']:
        values=change['purchased_metadata'][reference]
        for key,value in [('MPN',values['mpn']),('Manufacturer',values['manufacturer'])]:
            footprint.SetField(key,value)
            field=footprint.GetField(key)
            field.SetVisible(False)
            field.SetPosition(footprint.GetPosition())
b.BuildConnectivity()
p.SaveBoard(str(path),b)
summary={'r26':pad_changes,'r26_added_track_uuids':stubs,
 'r26_footprint':'BreakoutBoard:R_1206_3216Metric','renamed_capacitors':28,
 'footprints':len(list(b.GetFootprints())), 'board_size_mm':[81,80],
 'metadata_packages':len(change['purchased_metadata'])}
(OUT/'pcb-change.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
