"""First-order copper-path metrics; planes are not modeled as signal routes."""
from pathlib import Path
from collections import defaultdict, Counter
import json, math, networkx as nx
OUT=Path(__file__).resolve().parent
b=json.loads((OUT/'board_geometry.json').read_text())
cu={'Top','Bottom','GND','PWR'}
G=nx.Graph()
points=defaultdict(set)
def key(at,L,net):return (round(at[0],5),round(at[1],5),L,net)
def edge(a,z,w):
    if a!=z: G.add_edge(a,z,weight=w)
pads={}
for ref,f in b['footprints'].items():
    for pad in f['pads']:
        layers=set(pad['layers'])&cu
        ids=[key(pad['at'],L,pad['net']) for L in layers]
        pads[(ref,pad['number'])]=ids
        for node in ids: G.add_node(node); points[(node[2],node[3])].add(node)
        for a,z in zip(ids,ids[1:]):edge(a,z,0)
for t in b['tracks']:
    if t['type']=='via':
        ids=[key(t['start'],L,t['net']) for L in set(t['layers'])&cu]
        for node in ids: G.add_node(node); points[(node[2],node[3])].add(node)
        for a,z in zip(ids,ids[1:]):edge(a,z,0)
    else:
        for pos in ('start','end'):
            node=key(t[pos],t['layers'][0],t['net']); G.add_node(node);points[(node[2],node[3])].add(node)
for t in b['tracks']:
    if t['type']!='track':continue
    a,z=t['start'],t['end']; dx=z[0]-a[0];dy=z[1]-a[1]; length=math.hypot(dx,dy)
    if not length:continue
    on=[]
    for node in points[(t['layers'][0],t['net'])]:
        s=((node[0]-a[0])*dx+(node[1]-a[1])*dy)/(length*length)
        dist=abs((node[0]-a[0])*dy-(node[1]-a[1])*dx)/length
        if -1e-5<=s<=1+1e-5 and dist<1e-5:on.append((s,node))
    on.sort()
    for (s,n),(s2,n2) in zip(on,on[1:]):edge(n,n2,(s2-s)*length)
for ref,f in b['footprints'].items():
    for pad in f['pads']:
        ang=math.radians(pad['orientation']);co=math.cos(ang);si=math.sin(ang)
        for anchor in pads[(ref,pad['number'])]:
            for node in points[(anchor[2],anchor[3])]:
                dx=node[0]-anchor[0];dy=node[1]-anchor[1]
                x=dx*co-dy*si;y=dx*si+dy*co
                if abs(x)<=pad['size'][0]/2+.001 and abs(y)<=pad['size'][1]/2+.001:
                    edge(anchor,node,math.hypot(dx,dy))
# Passive R33 bridge explicitly adds the pad-center separation, not any copper on other nets.
for ref,f in b['footprints'].items():
    if ref.startswith('R') and f['value']=='33':
        for a in pads[(ref,'1')]:
            for z in pads[(ref,'2')]:edge(a,z,math.hypot(z[0]-a[0],z[1]-a[1]))
def route(ref1,pin1,ref2,pin2):
    options=[]
    for a in pads[(ref1,str(pin1))]:
        for z in pads[(ref2,str(pin2))]:
            try:
                path=nx.shortest_path(G,a,z,weight='weight')
                length=nx.path_weight(G,path,'weight')
                layers=sorted({a[2] for a,z in zip(path,path[1:]) if a[2]==z[2] and G[a][z]['weight']>0})
                options.append((length,layers))
            except nx.NetworkXNoPath:pass
    return min(options) if options else None
metrics={'routes':[],'total_net_track_mm':{},'bypass':[],'crystals':[],'source_resistors':[],'can_pairs':[]}
for name in ('SPI0_SCK','SPI0_MOSI','SPI0_MISO','SPI1_SCK','SPI1_MOSI','SPI1_MISO','VCC','GND'):
    tracks=[t for t in b['tracks'] if t['type']=='track' and t['net']==name]
    metrics['total_net_track_mm'][name]={'length_mm':sum(t['length'] for t in tracks),
        'layer_mm':{L:sum(t['length'] for t in tracks if L in t['layers']) for L in cu},
        'min_width_mm':min(t['width'] for t in tracks) if tracks else None}
for n in range(1,9):
    ref=f'U{n+8}';bus=(n-1)//4
    for signal,pin,header in [('SCK',9,[23,13][bus]),('MOSI',10,[19,37][bus]),('MISO',11,[21,22][bus])]:
        r=route('J1',header,ref,pin)
        metrics['routes'].append({'channel':n,'signal':signal,'planar_length_mm_including_R33_span':r[0] if r else None,'layers':r[1] if r else []})
    # Which bypass parts have a same-net, same-side direct routed feed from each rail pin?
    for pin in (1,14,25):
        pp=next(p for p in b['footprints'][ref]['pads'] if p['number']==str(pin))
        candidates=[]
        for cr,cf in b['footprints'].items():
            if not cr.startswith('CC'):continue
            rail=[p for p in cf['pads'] if p['net']==pp['net']]
            if rail:
                d=math.dist(pp['at'],rail[0]['at']);candidates.append((d,cr,rail[0]['number']))
        d,cr,cp=min(candidates)
        gpin=next(p['number'] for p in b['footprints'][cr]['pads'] if p['net']=='GND')
        local_return=route(ref,22,cr,gpin)
        metrics['bypass'].append({'channel':n,'pin':pin,'cap':cr,'rail_center_distance_mm':d,
            'pin22_return_without_planes':local_return})
    for pin in (20,21):metrics['crystals'].append({'channel':n,'pin':pin,'route':route(ref,pin,f'Y{n}',3 if pin==20 else 1)})
    conn=f'J{[4,5,7,8,9,10,11,12][n-1]}'
    rH=route(ref,4,conn,1); rL=route(ref,3,conn,2)
    metrics['can_pairs'].append({'channel':n,'CANH_route':rH,'CANL_route':rL,
        'length_difference_mm':abs(rH[0]-rL[0]) if rH and rL else None})
for r,header in [('R3',23),('R1',19),('R18',37),('R21',13)]:
    opts=[(route('J1',header,r,p),p) for p in (1,2)]
    valid=[(v,p) for v,p in opts if v]
    if valid:
        v,p=min(valid)
        metrics['source_resistors'].append({'ref':r,'header_pin':header,'pad':p,'header_to_resistor_mm':v[0]})
(OUT/'layout_metrics.json').write_text(json.dumps(metrics,indent=2))
print(json.dumps({k:v for k,v in metrics.items() if k not in ('routes','bypass','crystals')},indent=2))
print('SPI routes:',metrics['routes'])
print('VDD14 return without planes:',[v for v in metrics['bypass'] if v['pin']==14])
