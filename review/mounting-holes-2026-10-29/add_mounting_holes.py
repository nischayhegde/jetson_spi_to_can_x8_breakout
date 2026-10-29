"""Add four board-only M3 holes with copper and hardware clearance."""
from pathlib import Path
import hashlib
import json
import math
import shutil
import pcbnew as p

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
BOARD = ROOT / 'breakout/breakout.kicad_pcb'
LIBRARY = ROOT / 'kicad_footprints/BreakoutBoard.pretty'
NAME = 'MountingHole_3.2mm_M3_7mm_Keepout'
backup = OUT / 'before.kicad_pcb'
assert not backup.exists(), 'Backup already exists; do not repeat this mutation.'
b = p.LoadBoard(str(BOARD))
assert len(list(b.GetFootprints())) == 141
edge = next(d for d in b.GetDrawings() if d.GetLayer() == p.Edge_Cuts)
assert (p.ToMM(edge.GetStart().x), p.ToMM(edge.GetStart().y)) == (60, 47.5)
assert (p.ToMM(edge.GetEnd().x), p.ToMM(edge.GetEnd().y)) == (137, 127.5)

def vec(x, y):
    return p.VECTOR2I(p.FromMM(x), p.FromMM(y))

# Start with KiCad's standard unplated M3 hole; retain its exact drill geometry.
stock = Path(r'C:/Program Files/KiCad/10.0/share/kicad/footprints/MountingHole.pretty')
f = p.FootprintLoad(str(stock), 'MountingHole_3.2mm_M3')
assert f
f.SetFPID(p.LIB_ID('BreakoutBoard', NAME))
f.SetValue('M3 mounting hole')
f.SetLibDescription('3.2 mm NPTH for M3 hardware; 7 mm all-copper-layer keepout; 7.5 mm front/back courtyard; board-only')
f.SetAttributes(p.FP_EXCLUDE_FROM_BOM | p.FP_EXCLUDE_FROM_POS_FILES | p.FP_BOARD_ONLY)
f.Reference().SetText('REF**')
f.Reference().SetPosition(vec(0, 4.5))
f.Reference().SetTextSize(vec(.8, .8))
f.Reference().SetTextThickness(p.FromMM(.12))
f.Value().SetVisible(False)

# Both sides reserve space for the screw head, nut, or standoff.
for d in list(f.GraphicalItems()):
    if d.GetLayer() == p.F_CrtYd:
        d.SetEnd(vec(3.75, 0))
    elif d.GetLayer() == p.Cmts_User:
        d.SetEnd(vec(3.5, 0))
for layer, radius, width in [(p.B_CrtYd, 3.75, .05), (p.F_SilkS, 3.25, .12)]:
    circle = p.PCB_SHAPE(f)
    circle.SetShape(p.SHAPE_T_CIRCLE)
    circle.SetCenter(vec(0, 0))
    circle.SetEnd(vec(radius, 0))
    circle.SetWidth(p.FromMM(width))
    circle.SetLayer(layer)
    f.Add(circle)

# A circumscribed polygon guarantees at least 3.5 mm radial copper clearance.
# Footprint-owned keepouts move together with the mechanical hole.
z = p.ZONE(f)
z.SetIsRuleArea(True)
layers = p.LSET()
for layer in (p.F_Cu, p.In1_Cu, p.In2_Cu, p.B_Cu):
    layers.AddLayer(layer)
z.SetLayerSet(layers)
z.SetZoneName('M3 hardware - 7 mm copper-free')
z.SetDoNotAllowTracks(True)
z.SetDoNotAllowVias(True)
z.SetDoNotAllowPads(True)
z.SetDoNotAllowZoneFills(True)
z.SetDoNotAllowFootprints(False)
z.SetLocalClearance(0)
polygon = z.Outline()
polygon.NewOutline()
n = 96
radius = 3.5 / math.cos(math.pi/n)
for i in range(n):
    a = 2*math.pi*i/n
    pt = vec(radius*math.cos(a), radius*math.sin(a))
    polygon.Append(pt.x, pt.y)
# Exclude only the drill itself from the pad prohibition. Copper inside this
# opening is already prohibited by the board's 0.25 mm NPTH copper clearance.
hole_index = polygon.NewHole()
for i in range(n):
    a = -2*math.pi*i/n
    pt = vec(1.7*math.cos(a), 1.7*math.sin(a))
    polygon.Append(pt.x, pt.y, 0, hole_index)
f.Add(z)
p.FootprintSave(str(LIBRARY), f)
assert (LIBRARY / (NAME+'.kicad_mod')).exists()

shutil.copy2(BOARD, backup)
centers = {'H1':(60, 51.5), 'H2':(133, 51.5),
           'H3':(60, 123.5), 'H4':(133, 123.5)}
for ref, (x,y) in centers.items():
    hole = p.FootprintLoad(str(LIBRARY), NAME)
    hole.SetReference(ref)
    hole.SetPosition(vec(x, y))
    hole.SetLocked(True)
    # Put labels inward from each horizontal edge.
    hole.Reference().SetPosition(vec(x, y+(4.5 if ref in ('H1','H2') else -4.5)))
    b.Add(hole)
edge.SetStart(vec(56, 47.5))
b.BuildConnectivity()
p.SaveBoard(str(BOARD), b)

summary = {
    'original_size_mm':[77,80], 'new_size_mm':[81,80],
    'outline_mm':{'left':56,'top':47.5,'right':137,'bottom':127.5},
    'diameter_mm':3.2, 'hole_type':'non-plated through hole',
    'hole_centers_mm':centers, 'edge_inset_mm':4,
    'hole_spacing_mm':[73,72], 'copper_keepout_diameter_mm':7,
    'courtyard_diameter_mm':7.5, 'keepout_layers':['F.Cu','In1.Cu','In2.Cu','B.Cu'],
    'before_sha256':hashlib.sha256(backup.read_bytes()).hexdigest(),
    'after_sha256':hashlib.sha256(BOARD.read_bytes()).hexdigest(),
    'footprints':len(list(b.GetFootprints())),
}
(OUT/'change.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
