"""Regenerate fitted BOMs and order lists from the saved CAD and dated quotes.

Stock and prices are not refreshed by this command. See README.md.
"""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / 'review' / 'orderlist-2026-10-29'
RUNTIME = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node'


def run(args, **kwargs):
    return subprocess.run([str(x) for x in args], cwd=ROOT, check=True, **kwargs)


def main():
    found_cli = shutil.which('kicad-cli')
    kicad = Path(os.environ.get('KICAD_BIN') or
                 (str(Path(found_cli).parent) if found_cli else
                  'C:/Program Files/KiCad/10.0/bin'))
    cli = kicad / 'kicad-cli.exe'
    cad_python = kicad / 'python.exe'
    node = Path(os.environ.get('CODEX_NODE', str(RUNTIME / 'bin/node.exe')))
    modules = Path(os.environ.get('CODEX_ARTIFACT_NODE_MODULES', str(RUNTIME / 'node_modules')))
    for required in (cli, cad_python, node, modules / '@oai/artifact-tool'):
        if not required.exists():
            raise FileNotFoundError(f'Required runtime is missing: {required}')

    run([cli, 'sch', 'export', 'netlist', '--format', 'kicadxml', '--output',
         PIPELINE / 'schematic.net.xml', ROOT / 'breakout/breakout.kicad_sch'])
    run([cad_python, '-B', PIPELINE / 'extract_inventory.py'])
    run([sys.executable, '-B', PIPELINE / 'prepare_order_data.py'])

    # ESM package resolution requires an ancestor node_modules directory.
    # Remove only a junction created here, with a nonrecursive unlink.
    link = PIPELINE / 'node_modules'
    created_link = False
    if not link.exists():
        if os.name != 'nt':
            link.symlink_to(modules, target_is_directory=True)
        else:
            run(['cmd', '/c', 'mklink', '/J', link, modules], capture_output=True)
        created_link = True
    elif link.resolve() != modules.resolve():
        raise RuntimeError(f'Unexpected dependency directory: {link}')
    try:
        result = subprocess.run([str(node), str(PIPELINE / 'build_lists.mjs')],
                                cwd=ROOT, capture_output=True, text=True)
        print(result.stdout, end='')
        records = []
        for line in result.stdout.splitlines():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        complete = any(isinstance(r, dict) and
                       r.get('cadUnchangedDuringListGeneration') is True for r in records)
        if not complete or result.returncode not in (0, 1, 3221225477, -1073741819):
            print(result.stderr, file=sys.stderr)
            raise RuntimeError(f'Workbook generation failed (exit {result.returncode})')
        run([sys.executable, '-B', PIPELINE / 'add_native_hyperlinks.py'])
        run([sys.executable, '-B', PIPELINE / 'validate_lists.py'])
        if result.returncode:
            print(f'Artifact runtime exited with {result.returncode} after export; '
                  'independent workbook and CAD validation passed.')
        sidecar = ROOT / 'orderlist.xlsx.inspect.ndjson'
        if sidecar.exists():
            sidecar.replace(PIPELINE / sidecar.name)
    finally:
        if created_link:
            assert link.parent.resolve() == PIPELINE.resolve()
            assert link.resolve() == modules.resolve()
            if os.name == 'nt':
                os.rmdir(link)
            else:
                link.unlink()


if __name__ == '__main__':
    main()
