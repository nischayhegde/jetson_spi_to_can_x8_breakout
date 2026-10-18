"""Read placed schematic symbols without modifying the KiCad design."""
from collections import defaultdict
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent / 'breakout'


def children(text):
    """Yield direct child S-expressions, respecting quoted strings."""
    depth = 0
    quoted = escaped = False
    start = 0
    for i, char in enumerate(text):
        if escaped:
            escaped = False
        elif quoted and char == '\\':
            escaped = True
        elif char == '"':
            quoted = not quoted
        elif not quoted:
            if char == '(':
                if depth == 1:
                    start = i
                depth += 1
            elif char == ')':
                depth -= 1
                if depth == 1:
                    yield text[start:i + 1]
    if depth or quoted:
        raise ValueError('Unbalanced KiCad S-expression')


def property_value(block, name):
    match = re.search(r'\(property "' + re.escape(name) + r'" "([^"\n]*)"', block)
    return match[1] if match else ''


def placed_symbols():
    rows = []
    for path in sorted(PROJECT.rglob('*.kicad_sch')):
        for block in children(path.read_text(encoding='utf-8')):
            match = re.search(r'^\(symbol\s+\(lib_id "([^"]+)"', block)
            if not match:
                continue
            rows.append(dict(schematic=str(path.relative_to(ROOT.parent)),
                             lib_id=match[1], reference=property_value(block, 'Reference'),
                             value=property_value(block, 'Value'),
                             footprint=property_value(block, 'Footprint')))
    if not rows:
        raise ValueError('No placed schematic symbols found; refusing to infer an empty library')
    return rows


# Generic C/R symbols have no footprint assigned yet. Retain their selected
# packages rather than mistakenly treating them as unused library assets.
GENERIC_PARTS = {
    ('Device:C', '27p'): 'CL10C270JB8NNNC',
    ('Device:C', '1u'): 'CGA3E1X7R1E105K080AC',
    ('Device:C', '10u'): 'CL21B106KOQNNNE',
    ('Device:R', '33'): 'RC0603FR-0733RL',
    ('Device:R', '10k'): 'RC0603FR-0710KL',
    ('Device:R', '100k'): 'RC0603FR-07100KL',
    ('Device:R', '120'): 'RC1206FR-07120RL',
}


def active_selection(catalog_names):
    references = defaultdict(set)
    reasons = defaultdict(set)
    for row in placed_symbols():
        lib_id = row['lib_id']
        name = lib_id.split(':', 1)[1] if lib_id.startswith('BreakoutBoard:') else None
        reason = 'placed BreakoutBoard symbol'
        if name is None:
            name = GENERIC_PARTS.get((lib_id, row['value'].strip()))
            reason = 'package retained for placed generic C/R symbol'
            if lib_id in ('Device:C', 'Device:R') and name is None:
                raise ValueError('Unmapped generic passive: ' + str(row))
        if name:
            if name not in catalog_names:
                raise ValueError('Placed component missing from source catalog: ' + name)
            references[name].add(row['reference'])
            reasons[name].add(reason)

    # User explicitly requested a 1 A series fuse. It is missing from the saved
    # schematic, so preserve the selected part for the reported correction.
    if '0466001.NR' not in references:
        references['0466001.NR'] = set()
        reasons['0466001.NR'].add('retained for requested 1 A input fuse; absent from schematic')
    return {name: dict(references=sorted(refs), quantity=len(refs) or 1,
                       reason='; '.join(sorted(reasons[name])))
            for name, refs in references.items()}
