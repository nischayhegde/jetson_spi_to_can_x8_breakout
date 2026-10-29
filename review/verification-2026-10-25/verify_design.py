"""Reproducible read-only connectivity checks and first-order bandwidth model."""
from pathlib import Path
from collections import Counter
import csv, hashlib, json, math, xml.etree.ElementTree as ET
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
# Reuse the earlier per-channel net assertions and exhaustive logic evaluation,
# redirecting them to the current export. Do not execute its old summary/write stage.
code=(ROOT/'review/audit_latest.py').read_text().split("erc_path = OUT / 'erc_after.json'")[0]
code=code.replace("ROOT = Path(__file__).resolve().parent", "ROOT = Path(__file__).resolve().parents[1]")
code=code.replace("OUT = ROOT / 'latest'", "OUT = Path(__file__).resolve().parent")
exec(compile(code,'audit_latest_channel_checks','exec'))
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
erc=json.loads((OUT/'erc.json').read_text())
drc=json.loads((OUT/'drc.json').read_text())
violations=[v for s in erc['sheets'] for v in s['violations']]
summary={
 'input_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in [(ROOT/'breakout'/f'breakout.kicad_{suffix}') for suffix in ('sch','pcb','pro')]},
 'component_count':len(components), 'all_channel_checks_pass':all(all(r['checks'].values()) for r in rows),
 'channel_checks':rows,
 'gate_power':{r:net(r,14) for r in ('U1','U2','U4','U5')},
 'gate_bypass_correct':all(pair(f'CC0603KRX7R9BB{n}')=={'GND',net('U3',5)} for n in (5,6,7,17)),
 'fuses':{r:{'value':value(r),'nets':sorted(pair(r))} for r in components if r.startswith('F')},
 'header_ground_pins':[i for i in (6,9,14,20,25,30,34,39) if net('J1',i)=='GND'],
 'header_pins':{str(i):net('J1',i) for i in range(1,41)},
 'missing_footprints':[r for r,c in components.items() if not c.findtext('footprint')],
 'bank_truth_table':bank_table,
 'bank_idle_deselects_all':all(not r['selected'] for r in bank_table if r['native_cs0']==r['native_cs1']==1),
 'bank_single_select':all(len(r['selected'])==1 for r in bank_table if r['native_cs0']!=r['native_cs1']),
 'shared_irq_active_low':all(r['jetson_irq']==int(all(r['inputs'])) for r in irq_table),
 'erc':{'counts':dict(Counter(v['severity'] for v in violations)), 'types':dict(Counter(v['type'] for v in violations))},
 'drc':{k:len(drc.get(k,[])) for k in ('violations','unconnected_items','schematic_parity')},
 'protection_nets':{r:{str(i):net(r,i) for i in range(1,count+1)} for r,count in [('J6',2),('F1',2),('Q1',3),('D2',2),('R38',2),('C18',2),('C19',2),('C20',2),('U3',5)]},
 'bank_input_passives':{name:[r for r in components if r.startswith('R') and name in pair(r)] for name in ('GPIO_7','GPIO_11')}
}
(OUT/'electrical_audit.json').write_text(json.dumps(summary,indent=2))
with (OUT/'channel_audit.csv').open('w',newline='') as f:
    flat=[{k:v for k,v in r.items() if k!='checks'}|r['checks'] for r in rows]
    writer=csv.DictWriter(f,fieldnames=flat[0]); writer.writeheader(); writer.writerows(flat)
# Classical CAN, error-free data frames, includes three-bit intermission.
# No stuff bits provides a conservative upper bound on arrival rate.
# SPI model = RX timestamped object (12 + align4(DLC)), 5 byte READ_CRC
# overhead + CRC-protected 1-byte FIFO UINC write (6 bytes).
# Example unbatched model also reads two 4-byte status registers with CRC (18 bytes).
bandwidth=[]
for ext in (False,True):
  for dlc in (0,1,2,4,8):
    can_bits=(67 if ext else 47)+8*dlc
    frame_rate=1_000_000/can_bits
    obj=12+4*math.ceil(dlc/4)
    batched_bytes=obj+11 # command overhead per frame; status cost amortizes separately
    unbatched_bytes=batched_bytes+18
    tx_bytes=8+4*math.ceil(dlc/4)+5+6+12+5+6
    for bytes_per_frame,model in ((batched_bytes,'RX_CRC_amortized_status'),(unbatched_bytes,'RX_CRC_two_status_reads_per_frame'),
                                 (tx_bytes,'TX_CRC_and_timestamped_TEF_amortized_status'),
                                 (tx_bytes+18,'TX_CRC_and_TEF_two_status_reads_per_frame')):
      demand=4*frame_rate*bytes_per_frame*8
      bandwidth.append({'extended':ext,'dlc':dlc,'can_bits_min_including_intermission':can_bits,
        'frame_rate_upper_bound_per_channel':frame_rate, 'model':model,
        'spi_bytes_per_frame':bytes_per_frame, 'required_spi_mbit_per_bus':demand/1e6,
        'utilization_10MHz':demand/10e6,'utilization_16MHz':demand/16e6,'utilization_17MHz':demand/17e6,
        'gap_budget_us_per_frame_at_16MHz':1e6/(4*frame_rate)-bytes_per_frame*8/16,
        'total_eight_channel_frame_rate':8*frame_rate,
        'max_stuff_bits_bound':math.floor(((54 if ext else 34)+8*dlc-1)/4)})
example={
 'assumptions':'25 motors, 1 command and 1 feedback frame per update, DLC8, no retransmissions or extra telemetry',
 'update_rate_hz':1000,'frames_per_second':50000,
 'standard_CAN_total_utilization_across_eight_channels':50000*111/8_000_000,
 'extended_CAN_total_utilization_across_eight_channels':50000*131/8_000_000,
 'standard_bus_with_four_motors_utilization':4*2*1000*111/1e6,
 'extended_bus_with_four_motors_utilization':4*2*1000*131/1e6,
 'equal_bus_frame_rate':25000,
 'equal_bus_SPI_mbit_50percent_RX_TX_amortized_status':25000*(31+50)/2*8/1e6,
 'equal_bus_SPI_mbit_50percent_RX_TX_two_status_reads':25000*(49+68)/2*8/1e6,
}
(OUT/'bandwidth.json').write_text(json.dumps({'rows':bandwidth,'motor_example':example},indent=2))
with (OUT/'bandwidth.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=bandwidth[0]); w.writeheader(); w.writerows(bandwidth)
print(json.dumps({k:v for k,v in summary.items() if k not in ('channel_checks','bank_truth_table','header_pins','protection_nets')},indent=2))
print('Protection:',summary['protection_nets'])
print('Selected bandwidth rows:',json.dumps([r for r in bandwidth if r['dlc'] in (0,8)],indent=2))
