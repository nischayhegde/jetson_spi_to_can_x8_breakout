"""Remove CAD assets not needed by the active schematic and its mapped parts.

Run after build_library.py. Defaults to a reviewable plan; --apply deletes only
explicit files resolving inside kicad_footprints, with a ZIP backup first.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import zipfile

from library_usage import ROOT, PROJECT, children, placed_symbols


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    rows = json.loads((ROOT / 'parts.json').read_text())
    keep_symbols = {r['symbol'].split(':', 1)[1] for r in rows}
    symbol_file = ROOT / 'BreakoutBoard.kicad_sym'
    text = symbol_file.read_text(encoding='utf-8')
    blocks = list(children(text))
    named = {re.match(r'\(symbol "([^"]+)"', b)[1]: b for b in blocks
             if b.startswith('(symbol "')}
    assert keep_symbols <= named.keys(), keep_symbols - named.keys()
    assert {r['lib_id'].split(':', 1)[1] for r in placed_symbols()
            if r['lib_id'].startswith('BreakoutBoard:')} <= keep_symbols

    keep_fp = {r['footprint'].split(':', 1)[1] for r in rows}
    for r in placed_symbols():
        if r['footprint'].startswith('BreakoutBoard:'):
            keep_fp.add(r['footprint'].split(':', 1)[1])
    # Preserve explicitly assigned PCB footprints too, even before schematic
    # changes are synchronized. The current PCB is empty.
    for pcb in PROJECT.rglob('*.kicad_pcb'):
        keep_fp.update(re.findall(r'\(footprint "BreakoutBoard:([^"]+)"', pcb.read_text()))

    keep = {symbol_file.resolve()}
    for name in keep_fp:
        path = ROOT / 'BreakoutBoard.pretty' / (name + '.kicad_mod')
        assert path.is_file(), path
        keep.add(path.resolve())
        for model in re.findall(r'\(model "([^"]+)"', path.read_text()):
            resolved = Path(model.replace('${KIPRJMOD}', str(PROJECT))).resolve()
            assert resolved.is_relative_to(ROOT.resolve()), resolved
            assert resolved.is_file(), resolved
            keep.add(resolved)
    for row in rows:
        for name in row['step'].split(';'):
            assert (ROOT / name).resolve() in keep, name

    delete = {p.resolve() for p in ROOT.rglob('*')
              if p.is_file() and p.suffix.lower() in ('.step', '.stp', '.kicad_mod', '.kicad_sym')
              and p.resolve() not in keep}
    # Obsolete previews and the old powered-oscillator import instructions are
    # part of the same unused CAD bundle.
    previews = ROOT / 'validation' / 'symbols'
    delete.update(p.resolve() for p in previews.glob('*.svg')
                  if re.sub(r'_unit\d+(?:_demorgan)?$', '', p.stem) not in keep_symbols)
    old_oscillator = ROOT / 'SG-210STF_40.0000ML3'
    delete.update(p.resolve() for p in old_oscillator.rglob('*') if p.is_file())
    for path in delete:
        assert path.is_relative_to(ROOT.resolve()) and path != ROOT.resolve(), path

    backup = ROOT.parent / 'review' / 'latest' / 'library-before-cleanup.zip'
    previous_symbols = set(named)
    if backup.exists():
        with zipfile.ZipFile(backup) as archive:
            original = archive.read('kicad_footprints/BreakoutBoard.kicad_sym').decode('utf-8')
            previous_symbols.update(re.match(r'\(symbol "([^"]+)"', b)[1]
                                    for b in children(original) if b.startswith('(symbol "'))
    report = dict(
        schematic_sha256=hashlib.sha256((PROJECT / 'breakout.kicad_sch').read_bytes()).hexdigest(),
        retained_symbols=sorted(keep_symbols),
        retained_footprints=sorted(keep_fp),
        retained_step_models=sorted(str(p.relative_to(ROOT)).replace('\\', '/') for p in keep
                                  if p.suffix.lower() in ('.step', '.stp')),
        removed_symbols=sorted(previous_symbols - keep_symbols),
        deleted_files=sorted(str(p.relative_to(ROOT)).replace('\\', '/') for p in delete),
        component_usage=[{k: r[k] for k in ('mpn', 'quantity', 'symbol', 'footprint',
                                           'placed_references', 'retention_reason')} for r in rows],
        applied=args.apply,
    )
    if args.apply:
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            with zipfile.ZipFile(backup, 'w', zipfile.ZIP_DEFLATED) as archive:
                for path in ROOT.rglob('*'):
                    if path.is_file():
                        archive.write(path, path.relative_to(ROOT.parent))
        with zipfile.ZipFile(backup) as archive:
            assert archive.testzip() is None
        cleaned = [b for b in blocks if not b.startswith('(symbol "')
                   or re.match(r'\(symbol "([^"]+)"', b)[1] in keep_symbols]
        symbol_file.write_text('(kicad_symbol_lib\n' + '\n'.join(cleaned) + '\n)\n', encoding='utf-8')
        for path in sorted(delete):
            path.unlink()
        if old_oscillator.is_dir():
            # Only empty directories can be removed here; no recursive delete.
            for directory in sorted((p for p in old_oscillator.rglob('*') if p.is_dir()), reverse=True):
                directory.rmdir()
            old_oscillator.rmdir()
        hashes = {str(p.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted(keep)}
        (ROOT / 'sha256.json').write_text(json.dumps(hashes, indent=2) + '\n')
    (ROOT / 'cleanup_manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: len(report[k]) for k in ('retained_symbols', 'retained_footprints',
                                                'retained_step_models', 'deleted_files')}, indent=2))
    print('Applied:', args.apply)


if __name__ == '__main__':
    main()
