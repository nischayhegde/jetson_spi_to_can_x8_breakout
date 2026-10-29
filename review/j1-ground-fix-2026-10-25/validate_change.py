"""Validate only the requested seven pad/net changes and retain final evidence."""
from pathlib import Path
from collections import Counter
import hashlib, json, xml.etree.ElementTree as ET
import pcbnew as pcb
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
expected=[6,9,14,20,25,30,34,39]
added=[6,9,14,20,25,30,34]
def netmap(path):
    t=ET.parse(path).getroot()
    return {(n.attrib['ref'],n.attrib['pin']):net.attrib['name']
            for net in t.findall('./nets/net') for n in net.findall('node')}
old=netmap(ROOT/'review/verification-2026-10-25/breakout.net.xml')
new=netmap(OUT/'after.net.xml')
assert old.keys()==new.keys()
sch_changes={f'{r}.{p}':(old[(r,p)],new[(r,p)]) for r,p in old if old[(r,p)]!=new[(r,p)]}
assert set(sch_changes)=={f'J1.{p}' for p in added},sch_changes
assert all(new[('J1',str(p))]=='GND' for p in expected)
before=pcb.LoadBoard(str(OUT/'before.kicad_pcb'))
after=pcb.LoadBoard(str(ROOT/'breakout/breakout.kicad_pcb'))
def pads(b):
    return {(f.GetReference(),p.GetNumber()):(p.GetNetname(),p.GetPosition().x,p.GetPosition().y,p.GetOrientationDegrees(),p.GetSize().x,p.GetSize().y)
            for f in b.GetFootprints() for p in f.Pads()}
bp,ap=pads(before),pads(after)
assert bp.keys()==ap.keys()
pcb_changes={f'{r}.{p}':(bp[(r,p)][0],ap[(r,p)][0]) for r,p in bp if bp[(r,p)]!=ap[(r,p)]}
assert set(pcb_changes)==set(sch_changes),pcb_changes
assert all(bp[k][1:]==ap[k][1:] for k in bp)
def tracks(b):
    return {t.m_Uuid.AsString():(t.GetClass(),t.GetNetname(),t.GetStart().x,t.GetStart().y,t.GetEnd().x,t.GetEnd().y,
        t.GetLayer(),t.GetWidth(pcb.F_Cu) if isinstance(t,pcb.PCB_VIA) else t.GetWidth()) for t in b.GetTracks()}
assert tracks(before)==tracks(after)
assert len(list(before.GetFootprints()))==len(list(after.GetFootprints()))==141
erc=json.loads((OUT/'erc-after.json').read_text())
ev=[v for s in erc['sheets'] for v in s['violations']]
assert len(ev)==28 and all(v['type']=='lib_symbol_mismatch' and v['severity']=='warning' for v in ev),Counter(v['type'] for v in ev)
drc=json.loads((OUT/'drc-after.json').read_text())
assert all(not drc[k] for k in ('violations','unconnected_items','schematic_parity'))
result={'grounded_J1_pins':expected,'schematic_net_changes':sch_changes,'pcb_pad_net_changes':pcb_changes,
 'all_other_pad_nets_and_positions_unchanged':True,'existing_tracks_and_vias_unchanged':True,
 'footprints':141,'tracks_and_vias':len(tracks(after)), 'erc_errors':0,'erc_existing_library_warnings':28,
 'drc_violations':0,'unconnected_items':0,'schematic_pcb_mismatches':0,
 'final_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'breakout/breakout.kicad_sch',ROOT/'breakout/breakout.kicad_pcb']}}
(OUT/'final_validation.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
