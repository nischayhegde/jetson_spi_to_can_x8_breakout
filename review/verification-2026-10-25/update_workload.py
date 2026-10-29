"""Archive vendor protocol evidence and calculate user-specific traffic scenarios."""
from pathlib import Path
import csv, hashlib, json, urllib.request
import pymupdf
OUT=Path(__file__).resolve().parent
src=OUT/'sources/RobStride04_Manual.pdf'
url='https://www.robstride.com/assets/product_manual_robStride04-37549d59.pdf'
if not src.exists():
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
    content=urllib.request.urlopen(req,timeout=40).read()
    if not content.startswith(b'%PDF'):raise ValueError('Unexpected manual content')
    src.write_bytes(content)
doc=pymupdf.open(src)
(OUT/'sources/RobStride04_Manual.txt').write_text('\n'.join(f'\n=== PDF PAGE {i+1} ===\n'+p.get_text() for i,p in enumerate(doc)),encoding='utf-8')
matches=[]
for i,page in enumerate(doc):
    t=page.get_text()
    if ('1Mbps' in t or '1Mbps' in t.replace(' ','')) and ('29' in t):
        matches.append(i+1)
        page.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5)).save(str(OUT/f'RobStride04-protocol-p{i+1}.png'))
manifest=json.loads((OUT/'source_manifest.json').read_text())
manifest=[x for x in manifest if x['file']!=src.name]
manifest.append({'file':src.name,'url':url,'sha256':hashlib.sha256(src.read_bytes()).hexdigest()})
(OUT/'source_manifest.json').write_text(json.dumps(manifest,indent=2))
rows=[]
for motors in (2,3,4):
  for hz in (250,500,1000):
    fps=motors*hz*2
    rows.append({'motors_on_one_CAN_bus':motors,'command_and_feedback_rate_each_hz':hz,
      'frames_per_second':fps,'CAN_utilization_before_stuffing':fps*131/1e6,
      'CAN_utilization_max_stuff_bound':fps*160/1e6})
data={'user_inputs':{'Jetson_to_board_cable_length_cm':5,'nodes':'Mostly RobStride motors and IMUs',
  'motor_update_rate_hz':None,'motor_models_and_protocol_mode':None,'IMU_models_and_frame_schedule':None},
  'scenario_assumptions':'RobStride private protocol, Classical CAN 29-bit ID DLC8; one command and one response per update; IMU traffic excluded',
  'rows':rows,
  'example_IMU_budget':{'CAN_frames_per_second':1000,'assumed_extended_DLC8':True,
    'CAN_utilization_before_stuffing':.131,'CAN_utilization_max_stuff_bound':.160},
  'cable_delay_estimate':{'assumed_propagation_m_per_s':200_000_000,
    'one_way_ns':.05/200_000_000*1e9,'SCK_out_MISO_return_ns':2*.05/200_000_000*1e9,
    'comment':'Illustrative flight time only; actual cable impedance/capacitance/return path remain unmeasured'}}
(OUT/'robstride_workload.json').write_text(json.dumps(data,indent=2))
with (OUT/'robstride_workload.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
print('Vendor manual pages:',len(doc),'protocol pages:',matches,'bytes:',src.stat().st_size)
print(json.dumps(data,indent=2))
