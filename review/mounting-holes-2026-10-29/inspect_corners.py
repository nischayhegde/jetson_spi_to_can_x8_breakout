"""Find clear mounting-head envelopes without moving existing board features."""
from pathlib import Path
import json
import math
import pcbnew as p

ROOT = Path(__file__).resolve().parents[2]
b = p.LoadBoard(str(ROOT / 'breakout/breakout.kicad_pcb'))

def xy(v):
    return p.ToMM(v.x), p.ToMM(v.y)

boxes = []
for f in b.GetFootprints():
    box = f.GetBoundingBox(False, False)
    x, y = xy(box.GetOrigin())
    w, h = xy(box.GetSize())
    boxes.append((f.GetReference(), x, y, x+w, y+h))
tracks = []
for t in b.GetTracks():
    tracks.append((xy(t.GetStart()), xy(t.GetEnd()),
                   p.ToMM(t.GetWidth(p.F_Cu) if isinstance(t, p.PCB_VIA) else t.GetWidth())/2,
                   t.GetNetname(), b.GetLayerName(t.GetLayer())))

def clearance(x, y):
    results = []
    for ref, x0, y0, x1, y1 in boxes:
        results.append((math.hypot(max(x0-x, 0, x-x1), max(y0-y, 0, y-y1)), ref))
    for (ax, ay), (bx, by), r, net, layer in tracks:
        dx, dy = bx-ax, by-ay
        u = max(0, min(1, ((x-ax)*dx+(y-ay)*dy)/(dx*dx+dy*dy))) if dx or dy else 0
        results.append((math.hypot(x-ax-u*dx, y-ay-u*dy)-r, f'{net} on {layer}'))
    return min(results)

# Require a 7 mm diameter envelope and 0.25 mm board-edge margin.
envelope = 3.5
inset = 3.75
best = []
for xl in [55+i*.25 for i in range(41)]:
    for yt in [44+i*.25 for i in range(37)]:
        yb = 175-yt  # symmetric about the original board center y=87.5
        xr = 133.25
        cs = [clearance(xl,yt),clearance(xl,yb),clearance(xr,yt),clearance(xr,yb)]
        if min(v[0] for v in cs) < envelope:
            continue
        outline = [min(60, xl-inset), min(47.5, yt-inset),
                   max(137, xr+inset), max(127.5, yb+inset)]
        width, height = outline[2]-outline[0], outline[3]-outline[1]
        best.append({'area':width*height, 'size':[width,height],
                     'centers':[[xl,yt],[xr,yt],[xl,yb],[xr,yb]],
                     'outline':outline, 'clearances':cs})
best.sort(key=lambda x:x['area'])
out = {'minimum_area_options':best[:12],
       'original_corner_checks':{str(pt):clearance(*pt) for pt in [(63.75,51.25),(133.25,51.25),(63.75,123.75),(133.25,123.75)]}}
(Path(__file__).parent/'corner-analysis.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
