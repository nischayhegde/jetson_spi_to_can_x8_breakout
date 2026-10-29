"""Assign the seven ground pads to GND and refill the existing planes."""
from pathlib import Path
import hashlib, json, shutil
import pcbnew as pcb
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
path=ROOT/'breakout/breakout.kicad_pcb'
backup=OUT/'before.kicad_pcb'
if backup.exists():raise RuntimeError('Backup already exists; do not repeat mutation')
board=pcb.LoadBoard(str(path))
j=next(f for f in board.GetFootprints() if f.GetReference()=='J1')
pads={int(p.GetNumber()):p for p in j.Pads()}
ground=board.FindNet('GND')
assert ground and ground.GetNetCode()>0
assert pads[39].GetNetname()=='GND'
pins=[6,9,14,20,25,30,34]
before={p:pads[p].GetNetname() for p in pins}
assert all(before[p]==f'unconnected-(J1-Pin_{p}-Pad{p})' for p in pins)
raw=path.read_bytes();shutil.copy2(path,backup)
for p in pins:
    pads[p].SetNet(ground)
    pads[p].SetPinType('passive')
board.BuildConnectivity()
filler=pcb.ZONE_FILLER(board)
filler.Fill(board.Zones())
pcb.SaveBoard(str(path),board)
result={'added_ground_pins':pins,'before_nets':before,'after_nets':{p:pads[p].GetNetname() for p in pins},
        'existing_ground_pin':39,'footprints':len(list(board.GetFootprints())),
        'track_and_via_count':len(list(board.GetTracks())),
        'before_sha256':hashlib.sha256(raw).hexdigest(),'after_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
(OUT/'pcb_change.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
