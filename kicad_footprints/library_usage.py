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
    pending = [PROJECT / 'breakout.kicad_sch']
    visited = set()
    while pending:
        path = pending.pop().resolve()
        if path in visited:
            continue
        visited.add(path)
        blocks = list(children(path.read_text(encoding='utf-8')))
        for block in blocks:
            if re.match(r'^\(sheet\s', block):
                sheet_file = property_value(block, 'Sheetfile')
                if sheet_file:
                    pending.append(path.parent / sheet_file)
        for block in blocks:
            match = re.search(r'^\(symbol\s+\(lib_id "([^"]+)"', block)
            if not match:
                continue
            rows.append(dict(schematic=str(path.relative_to(ROOT.parent)),
                             lib_id=match[1], reference=property_value(block, 'Reference'),
                             value=property_value(block, 'Value'),
                             footprint=property_value(block, 'Footprint'),
                             mpn=property_value(block, 'MPN'),
                             manufacturer=property_value(block, 'Manufacturer')))
    if not rows:
        raise ValueError('No placed schematic symbols found; refusing to infer an empty library')
    return rows


# Compatibility mappings for earlier generic symbols. Current placements carry
# explicit MPN and Manufacturer fields shared with the PCB and purchasing list.
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
    footprints = defaultdict(set)
    manufacturers = defaultdict(set)
    for row in placed_symbols():
        lib_id = row['lib_id']
        name = row['mpn'].replace('MCP251863T-E/SS','MCP251863T-E_SS') if row['mpn'] else None
        if name is None and lib_id.startswith('BreakoutBoard:'):
            name = lib_id.split(':', 1)[1]
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
            footprints[name].add(row['footprint'])
            if row['manufacturer']:manufacturers[name].add(row['manufacturer'])
    return {name: dict(references=sorted(refs), quantity=len(refs),
                       footprints=sorted(footprints[name]),
                       manufacturer='; '.join(sorted(manufacturers[name])),
                       reason='; '.join(sorted(reasons[name])))
            for name, refs in references.items()}
