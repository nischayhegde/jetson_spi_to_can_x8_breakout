"""Validate the bundle with KiCad's actual footprint reader and pin mapping checks.
Run using C:/Program Files/KiCad/10.0/bin/python.exe.
"""
from pathlib import Path
import json
import re
import hashlib
import pcbnew

root=Path(__file__).resolve().parent
text=(root/'BreakoutBoard.kicad_sym').read_text(encoding='utf-8')

def block(start):
    depth=0; quoted=False; escaped=False
    for i in range(start,len(text)):
        c=text[i]
        if escaped: escaped=False
        elif c=='\\' and quoted: escaped=True
        elif c=='"': quoted=not quoted
        elif not quoted:
            if c=='(': depth+=1
            elif c==')':
                depth-=1
                if not depth:return text[start:i+1]
    raise AssertionError('Unbalanced S-expression')

def pins(name):
    s=block(text.index('(symbol "'+name+'"'))
    return set(re.findall(r'\(number "([^"]+)"',s))

report=[]
for row in json.loads((root/'parts.json').read_text()):
    name=row['symbol'].split(':')[1]
    namespace,fname=row['footprint'].split(':')
    library=root/'BreakoutBoard.pretty' if namespace=='BreakoutBoard' else Path(r'C:/Program Files/KiCad/10.0/share/kicad/footprints')/(namespace+'.pretty')
    fp=pcbnew.FootprintLoad(str(library),fname)
    assert fp is not None, fname
    pads={p.GetNumber() for p in fp.Pads() if p.GetNumber()}
    assert pins(name)==pads,(name,pins(name),pads)
    for step in row['step'].split(';'):
        b=(root/step).read_bytes()
        assert b.startswith(b'ISO-10303-21;'),step
        assert b'END-ISO-10303-21;' in b,step
    report.append(f'PASS {row["mpn"]}: symbol pins match pads {sorted(pads)}; STEP exists and has ISO-10303 header/trailer')
assert pins('MCP251863T-E_SS')=={str(i) for i in range(1,29)}
mcpsymbol=block(text.index('(symbol "MCP251863T-E_SS"'))
for number,kind in [('23','input'),('28','output')]:
    candidates=[]
    for match in re.finditer(r'\(pin \w+ line',mcpsymbol):
        # The block reader uses the complete library, so translate the offset.
        start=text.index('(symbol "MCP251863T-E_SS"')+match.start()
        pin=block(start)
        if '(number "'+number+'"' in pin:candidates.append(pin)
    assert len(candidates)==1 and candidates[0].startswith('(pin '+kind+' '),(number,kind)
report.append('PASS manufacturer MCP251863 pin directions: TXD23 input; RXD28 output')
for name,expected in [('AO3401A',{'1':'G','2':'S','3':'D'}),
                      ('BZT52C6V8-13-F',{'1':'K','2':'A'})]:
    start=text.index('(symbol "'+name+'"')
    s=block(start)
    actual={}
    for match in re.finditer(r'\(pin \w+ line',s):
        pin=block(start+match.start())
        actual[re.search(r'\(number "([^"]+)"',pin)[1]]=re.search(r'\(name "([^"]+)"',pin)[1]
    assert actual==expected,(name,actual,expected)
    report.append(f'PASS manufacturer {name} pin identities: {actual}')
for row in json.loads((root/'parts.json').read_text()):
    if row['asset_origin'] in ('Device:C','Device:R'):
        s=block(text.index('(symbol "'+row['symbol'].split(':')[1]+'"'))
        expected='C' if row['asset_origin']=='Device:C' else 'R'
        assert re.search(r'\(property "Reference" "'+expected+'"',s),row['mpn']
report.append('PASS standard C/R reference prefixes on passive aliases')
for name,digest in json.loads((root/'sha256.json').read_text()).items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,name
report += ['PASS SHA-256 inventory', 'KiCad footprint reader: '+pcbnew.GetBuildVersion(),
           'These checks validate file loading and pin-number coverage, not electrical correctness or manufacturer mechanical tolerances.']
(root/'validation'/'report.txt').write_text('\n'.join(report)+'\n',encoding='utf-8')
print('\n'.join(report))
