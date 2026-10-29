"""Keep the NPTH drill out of its surrounding copper keepout's pad rule."""
from pathlib import Path
import math
import pcbnew as p

ROOT = Path(__file__).resolve().parents[2]
lib = ROOT/'kicad_footprints/BreakoutBoard.pretty'
name = 'MountingHole_3.2mm_M3_7mm_Keepout'
path = ROOT/'breakout/breakout.kicad_pcb'
b = p.LoadBoard(str(path))
f = p.FootprintLoad(str(lib), name)
for footprint in [f]+[x for x in b.GetFootprints() if x.GetReference() in ('H1','H2','H3','H4')]:
    for zone in footprint.Zones():
        polygon = zone.Outline()
        assert polygon.HoleCount(0) == 0
        h = polygon.NewHole()
        center = footprint.GetPosition()
        for i in range(96):
            a = -2*math.pi*i/96
            polygon.Append(center.x+p.FromMM(1.7*math.cos(a)),
                           center.y+p.FromMM(1.7*math.sin(a)), 0, h)
p.FootprintSave(str(lib), f)
p.SaveBoard(str(path), b)
print('Updated all four hardware keepouts and the project footprint.')
