"""Verify the mechanical change preserves the complete existing layout."""
from pathlib import Path
import hashlib
import json
import math
import re
import pcbnew as p

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
path = ROOT/'breakout/breakout.kicad_pcb'
before = p.LoadBoard(str(OUT/'before.kicad_pcb'))
after = p.LoadBoard(str(path))

def xy(v):
    return v.x, v.y

def footprints(board):
    return {f.GetReference():f for f in board.GetFootprints()}

def footprint_data(f):
    return (f.m_Uuid.AsString(), f.GetFPID().GetUniStringLibId(), f.GetValue(),
            xy(f.GetPosition()), f.GetOrientationDegrees(), f.GetLayer(),
            f.GetAttributes(),
            {pad.m_Uuid.AsString():(pad.GetNumber(), pad.GetNetname(),
                xy(pad.GetPosition()), pad.GetOrientationDegrees(),
                xy(pad.GetSize()), xy(pad.GetDrillSize()),
                pad.GetShape(), pad.GetAttribute(), tuple(pad.GetLayerSet().Seq()))
             for pad in f.Pads()})

def tracks(board):
    return {t.m_Uuid.AsString():(t.GetClass(), t.GetNetname(), xy(t.GetStart()),
        xy(t.GetEnd()), tuple(t.GetLayerSet().Seq()),
        t.GetWidth(p.F_Cu) if isinstance(t,p.PCB_VIA) else t.GetWidth(),
        t.GetDrillValue() if isinstance(t,p.PCB_VIA) else None)
        for t in board.GetTracks()}

bf, af = footprints(before), footprints(after)
assert len(bf) == 141 and len(af) == 145
assert set(af)-set(bf) == {'H1','H2','H3','H4'}
assert all(footprint_data(f)==footprint_data(af[ref]) for ref,f in bf.items())
assert tracks(before) == tracks(after)
assert len(list(before.GetDrawings())) == len(list(after.GetDrawings()))
edge = next(d for d in after.GetDrawings() if d.GetLayer()==p.Edge_Cuts)
assert xy(edge.GetStart()) == (p.FromMM(56),p.FromMM(47.5))
assert xy(edge.GetEnd()) == (p.FromMM(137),p.FromMM(127.5))

expected = {'H1':(60,51.5),'H2':(133,51.5),'H3':(60,123.5),'H4':(133,123.5)}
for ref, center in expected.items():
    f = af[ref]
    assert xy(f.GetPosition()) == tuple(p.FromMM(x) for x in center)
    assert f.IsLocked()
    assert f.GetAttributes() == p.FP_BOARD_ONLY|p.FP_EXCLUDE_FROM_BOM|p.FP_EXCLUDE_FROM_POS_FILES
    pads = list(f.Pads())
    assert len(pads)==1 and pads[0].GetAttribute()==p.PAD_ATTRIB_NPTH
    assert xy(pads[0].GetDrillSize()) == (p.FromMM(3.2),p.FromMM(3.2))
    zones = list(f.Zones())
    assert len(zones)==1
    z = zones[0]
    assert z.GetIsRuleArea()
    assert set(z.GetLayerSet().Seq()) == {p.F_Cu,p.In1_Cu,p.In2_Cu,p.B_Cu}
    assert z.GetDoNotAllowTracks() and z.GetDoNotAllowVias()
    assert z.GetDoNotAllowPads() and z.GetDoNotAllowZoneFills()

# Inspect saved plane polygons on every copper layer inside each head envelope.
sample_count = 0
for x,y in expected.values():
    for layer in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.B_Cu):
        for zone in after.Zones():
            if not zone.GetIsRuleArea() and zone.IsOnLayer(layer):
                polys = zone.GetFilledPolysList(layer)
                for radius in (0,1.8,2.5,3.45):
                    for i in range(64):
                        a = 2*math.pi*i/64
                        point = p.VECTOR2I(p.FromMM(x+radius*math.cos(a)),
                                           p.FromMM(y+radius*math.sin(a)))
                        assert not polys.Contains(point), (x,y,layer,radius,i)
                        sample_count += 1

drc = json.loads((OUT/'drc-after.json').read_text())
assert all(not drc[k] for k in ('violations','unconnected_items','schematic_parity'))
drill = (OUT/'drill/breakout-NPTH.drl').read_text()
assert 'T1C3.200' in drill
hits = re.findall(r'^X([\d.]+)Y(-?[\d.]+)$',drill,re.M)
assert len(hits)==4
assert {(float(x),-float(y)) for x,y in hits} == set(expected.values())

summary = json.loads((OUT/'change.json').read_text())
summary.update({
    'after_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
    'all_141_existing_footprints_and_pad_nets_unchanged':True,
    'all_existing_tracks_and_vias_unchanged':True,
    'existing_tracks_and_vias':len(tracks(after)),
    'drc_violations':0,'unconnected_items':0,'schematic_parity_issues':0,
    'npth_drill_hits':4,'kicad_version':p.Version(),
    'saved_zone_copper_free_sample_checks':sample_count,
})
(OUT/'validation.json').write_text(json.dumps(summary,indent=2)+'\n')
(OUT/'change.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
