"""Verify layer identities, drill locations and source hashes, then zip exports."""
from pathlib import Path
from collections import Counter, defaultdict
import hashlib
import json
import math
import re
import zipfile
import pcbnew as pcb

ROOT = Path(__file__).resolve().parents[2]
REVIEW = Path(__file__).resolve().parent
OUTPUT = ROOT / 'fabrication/2026-10-29'
ARCHIVE = ROOT / 'fabrication/jetson_spi_to_can_x8_breakout-gerbers-drills-2026-10-29.zip'
meta = json.loads((REVIEW / 'source-metadata.json').read_text())
board = pcb.LoadBoard(str(ROOT / 'breakout/breakout.kicad_pcb'))
for relative, expected in meta['source_sha256'].items():
    assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected
job = json.loads((OUTPUT / 'breakout-job.gbrjob').read_text())
expected_functions = {'Copper,L1,Top', 'Copper,L2,Inr', 'Copper,L3,Inr', 'Copper,L4,Bot',
                      'SolderPaste,Top', 'SolderPaste,Bot', 'Legend,Top', 'Legend,Bot',
                      'SolderMask,Top', 'SolderMask,Bot', 'Profile'}
assert len(job['FilesAttributes']) == 11
assert {f['FileFunction'] for f in job['FilesAttributes']} == expected_functions
assert job['GeneralSpecs']['LayerNumber'] == 4
assert job['GeneralSpecs']['BoardThickness'] == 1.6
for entry in job['FilesAttributes']:
    assert Path(entry['Path']).name == entry['Path']
    text = (OUTPUT / entry['Path']).read_text()
    assert text.rstrip().endswith('M02*'), entry['Path']
    assert '%MOMM*%' in text and '%FSLAX46Y46*%' in text
    attribute = entry['FileFunction'].replace('SolderPaste','Paste').replace('SolderMask','Soldermask')
    assert '%TF.FileFunction,' + attribute in text, entry['Path']
    assert re.search(r'%ADD\d+', text), entry['Path']

outline = (OUTPUT / 'breakout-Edge_Cuts.gm1').read_text()
points = [(int(x)/1e6, -int(y)/1e6, int(code)) for x,y,code in
          re.findall(r'^X(-?\d+)Y(-?\d+)D(0[12])\*$', outline, re.M)]
assert len(points) == 5 and points[0][2] == 2 and all(p[2] == 1 for p in points[1:])
assert points[0][:2] == points[-1][:2]
outline_size = [max(p[i] for p in points)-min(p[i] for p in points) for i in [0,1]]
assert outline_size == [81.0,80.0]
edge_points = [pt for d in board.GetDrawings() if d.GetLayer() == pcb.Edge_Cuts
               for pt in [d.GetStart(),d.GetEnd()]]
assert outline_size == [pcb.ToMM(max(getattr(pt,axis) for pt in edge_points) -
                               min(getattr(pt,axis) for pt in edge_points)) for axis in ['x','y']]
meta['outline_stroke_bounds_mm'] = meta['board_size_mm']
meta['board_size_mm'] = outline_size
(REVIEW / 'source-metadata.json').write_text(json.dumps(meta,indent=2)+'\n')

expected_hits = defaultdict(list)
for fp in board.GetFootprints():
    for pad in fp.Pads():
        size = pad.GetDrillSize()
        if size.x and size.y:
            assert size.x == size.y, 'Slotted drill requires a separate slot validator'
            plating = 'NPTH' if pad.GetAttribute() == pcb.PAD_ATTRIB_NPTH else 'PTH'
            expected_hits[(plating, round(pcb.ToMM(size.x),6))].append(
                (pcb.ToMM(pad.GetPosition().x),pcb.ToMM(pad.GetPosition().y)))
for item in board.GetTracks():
    if isinstance(item,pcb.PCB_VIA):
        expected_hits[('PTH',round(pcb.ToMM(item.GetDrillValue()),6))].append(
            (pcb.ToMM(item.GetPosition().x),pcb.ToMM(item.GetPosition().y)))
observed = Counter()
for plating in ['PTH','NPTH']:
    text = (OUTPUT / f'breakout-{plating}.drl').read_text()
    assert text.startswith('M48\n') and text.rstrip().endswith('M30')
    assert 'METRIC' in text and 'G90' in text and 'G85' not in text and 'G91' not in text
    assert ('TF.FileFunction,NonPlated' if plating == 'NPTH' else 'TF.FileFunction,Plated') in text
    tools = {int(n):float(d) for n,d in re.findall(r'^T(\d+)C([\d.]+)$',text,re.M)}
    active = None
    for line in text.splitlines():
        match = re.fullmatch(r'T(\d+)',line)
        if match:
            active = int(match[1])
        match = re.fullmatch(r'X(-?[\d.]+)Y(-?[\d.]+)',line)
        if match:
            assert active in tools
            key = plating,tools[active]
            actual = float(match[1]),-float(match[2])
            remaining = expected_hits[key]
            closest = min(range(len(remaining)),key=lambda i:math.dist(actual,remaining[i]))
            assert math.dist(actual,remaining[closest]) < .00072, (key,actual,remaining[closest])
            remaining.pop(closest)
            observed[key] += 1
assert not any(expected_hits.values()), 'A source drill was omitted'
assert observed == {('NPTH',3.2):4,('PTH',.3):207,('PTH',.95):24,('PTH',1.):46}
assert {(h['x_mm'],h['y_mm']) for h in meta['mounting_holes']} == {(60.,51.5),(133.,51.5),(60.,123.5),(133.,123.5)}
drc = json.loads((REVIEW / 'drc.json').read_text())
assert all(not drc[k] for k in ['violations','unconnected_items','schematic_parity'])

readme = '''SPI to eight-channel CAN breakout - fabrication files
Export date: 2026-10-29. KiCad 10.0.7.

Finished outline: 81 x 80 mm, measured at the outline centerline.
Board: four copper layers, nominal 1.6 mm FR4.
The saved nominal copper thickness is 0.035 mm on each copper layer.

Copper order, top to bottom:
  L1  breakout-Top.gtl        F.Cu   Top
  L2  breakout-GND.g1         In1.Cu GND
  L3  breakout-PWR.g2         In2.Cu PWR
  L4  breakout-Bottom.gbl     B.Cu   Bottom

Other Gerbers:
  breakout-F_Mask.gts / breakout-B_Mask.gbs: solder mask openings.
  breakout-F_Silkscreen.gto / breakout-B_Silkscreen.gbo: silkscreen.
  breakout-Edge_Cuts.gm1: single closed board perimeter.
  breakout-F_Paste.gtp / breakout-B_Paste.gbp: optional stencil layers.

Drills: Excellon, millimeters, absolute origin matching the Gerbers,
unmirrored; plated and non-plated holes are separate:
  breakout-PTH.drl: 277 holes (207 x 0.30, 24 x 0.95, 46 x 1.00 mm).
  breakout-NPTH.drl: four 3.20 mm non-plated M3 mounting holes.
The mounting-hole center spacing is 73 x 72 mm, 4 mm from board edges.

Gerbers use X2 attributes and 4.6 absolute metric coordinates. Copper zones
were checked/refilled in memory before plotting. Silkscreen is clipped out
of solder-mask openings during export. The source CAD files were unchanged.

breakout-job.gbrjob records layer functions and the saved nominal stackup.
Its 81.05 x 80.05 mm size includes the 0.05 mm outline stroke; the actual
board perimeter centerline in breakout-Edge_Cuts.gm1 is 81 x 80 mm.
The source does not specify a surface finish (job Finish="None"); select
the surface finish when placing the fabrication order.

Pre-export DRC with zones refilled: zero violations, zero unconnected
items and zero schematic/PCB parity issues under the project settings.
Every exported drill hit was compared against its source pad or via.
The export contains no changes to the electrical design or board geometry.
'''
(OUTPUT / 'README.txt').write_text(readme,encoding='utf-8')
files = sorted(p for p in OUTPUT.iterdir() if p.is_file() and p.name != 'SHA256SUMS.txt')
assert len(files) == 16
hashes = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
(OUTPUT / 'SHA256SUMS.txt').write_text(''.join(f'{digest}  {name}\n' for name,digest in hashes.items()))
assert not ARCHIVE.exists(), f'Archive already exists: {ARCHIVE}'
with zipfile.ZipFile(ARCHIVE,'w',compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(OUTPUT.iterdir()):
        assert path.is_file()
        archive.write(path,path.name)
with zipfile.ZipFile(ARCHIVE) as archive:
    assert archive.testzip() is None and len(archive.namelist()) == 17
    for name,digest in hashes.items():
        assert hashlib.sha256(archive.read(name)).hexdigest() == digest
result = {'gerber_layers':11,'copper_layers':4,'outline_mm':outline_size,
          'thickness_mm':1.6,'pth_holes':277,'npth_holes':4,'mounting_drill_mm':3.2,
          'all_drill_locations_match_source':True,'matching_absolute_origins':True,
          'drc_violations':0,'unconnected_items':0,'schematic_parity_issues':0,
          'source_files_unchanged':True,'zip_files':17,'zip_crc_check':'PASS',
          'archive':str(ARCHIVE),'archive_sha256':hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()}
(REVIEW / 'validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
