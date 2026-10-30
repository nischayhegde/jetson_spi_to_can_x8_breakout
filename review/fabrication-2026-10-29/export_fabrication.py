"""Export the saved board without changing the PCB, schematic or project."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import subprocess
import pcbnew as pcb

ROOT = Path(__file__).resolve().parents[2]
REVIEW = Path(__file__).resolve().parent
OUTPUT = ROOT / 'fabrication/2026-10-29'
CLI = Path('C:/Program Files/KiCad/10.0/bin/kicad-cli.exe')
BOARD = ROOT / 'breakout/breakout.kicad_pcb'
sources = [BOARD, BOARD.with_suffix('.kicad_sch'), BOARD.with_suffix('.kicad_pro')]
hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
assert not OUTPUT.exists(), f'Output directory already exists: {OUTPUT}'
OUTPUT.mkdir(parents=True)
(REVIEW / 'source-sha256.json').write_text(json.dumps(hashes, indent=2) + '\n')

def run(name, args):
    result = subprocess.run([str(CLI), *map(str, args)], cwd=ROOT,
                            capture_output=True, text=True)
    (REVIEW / (name + '.log')).write_text(result.stdout + result.stderr, encoding='utf-8')
    print(result.stdout, end='', flush=True)
    result.check_returncode()

run('drc', ['pcb', 'drc', '--format', 'json', '--schematic-parity',
            '--severity-all', '--exit-code-violations', '--refill-zones',
            '--output', REVIEW / 'drc.json', BOARD])
drc = json.loads((REVIEW / 'drc.json').read_text())
assert all(not drc[k] for k in ['violations', 'unconnected_items', 'schematic_parity'])
layers = ['F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu', 'F.Mask', 'B.Mask',
          'F.Silkscreen', 'B.Silkscreen', 'F.Paste', 'B.Paste', 'Edge.Cuts']
run('gerbers', ['pcb', 'export', 'gerbers', '--output', str(OUTPUT) + '/',
                '--layers', ','.join(layers), '--precision', '6',
                '--check-zones', '--subtract-soldermask', BOARD])
run('drills', ['pcb', 'export', 'drill', '--output', str(OUTPUT) + '/',
               '--format', 'excellon', '--drill-origin', 'absolute',
               '--excellon-units', 'mm', '--excellon-zeros-format', 'decimal',
               '--excellon-separate-th', '--generate-map', '--map-format', 'svg',
               '--generate-report', '--report-path', OUTPUT / 'drill-report.txt', BOARD])
for svg in OUTPUT.glob('*.svg'):
    svg.replace(REVIEW / svg.name)

board = pcb.LoadBoard(str(BOARD))
drill_counts = Counter()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        size = pad.GetDrillSize()
        if size.x and size.y:
            plating = 'NPTH' if pad.GetAttribute() == pcb.PAD_ATTRIB_NPTH else 'PTH'
            drill_counts[(plating, round(pcb.ToMM(size.x), 6), round(pcb.ToMM(size.y), 6))] += 1
via_count = 0
for track in board.GetTracks():
    if isinstance(track, pcb.PCB_VIA):
        via_count += 1
        diameter = round(pcb.ToMM(track.GetDrillValue()), 6)
        drill_counts[('PTH', diameter, diameter)] += 1
box = board.GetBoardEdgesBoundingBox()
edge_points = [pt for drawing in board.GetDrawings() if drawing.GetLayer() == pcb.Edge_Cuts
               for pt in [drawing.GetStart(), drawing.GetEnd()]]
outline_size = [pcb.ToMM(max(getattr(pt, axis) for pt in edge_points) -
                        min(getattr(pt, axis) for pt in edge_points)) for axis in ['x', 'y']]
meta = {'source_sha256': hashes, 'kicad_version': pcb.GetBuildVersion(),
        'board_size_mm': outline_size,
        'outline_stroke_bounds_mm': [pcb.ToMM(box.GetWidth()), pcb.ToMM(box.GetHeight())],
        'board_thickness_mm': pcb.ToMM(board.GetDesignSettings().GetBoardThickness()),
        'copper_layers': board.GetCopperLayerCount(), 'via_count': via_count,
        'footprints': len(list(board.GetFootprints())),
        'drill_counts': [{'plating': k[0], 'x_mm': k[1], 'y_mm': k[2], 'count': v}
                         for k, v in sorted(drill_counts.items())],
        'mounting_holes': [{'reference': fp.GetReference(),
                            'x_mm': pcb.ToMM(fp.GetPosition().x),
                            'y_mm': pcb.ToMM(fp.GetPosition().y),
                            'drill_mm': pcb.ToMM(next(iter(fp.Pads())).GetDrillSize().x)}
                           for fp in board.GetFootprints() if fp.GetReference() in ['H1','H2','H3','H4']]}
assert all(hashlib.sha256(p.read_bytes()).hexdigest() == hashes[str(p.relative_to(ROOT))] for p in sources)
meta['source_files_unchanged'] = True
(REVIEW / 'source-metadata.json').write_text(json.dumps(meta, indent=2) + '\n')
print(json.dumps(meta, indent=2), flush=True)
