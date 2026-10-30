"""Create precise PCB assembly maps and a printable guide from extracted CAD.

Package outlines, pad centers, pad sizes, drills and rotations come from KiCad.
Only documentation is authored; the source design is never edited.
"""
from pathlib import Path
from collections import Counter, defaultdict
import csv, hashlib, json, math, re
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT=Path(__file__).resolve().parents[2]
REVIEW=Path(__file__).resolve().parent
OUT=ROOT/'output/assembly'
PDF=ROOT/'output/pdf/pcb-assembly-guide.pdf'
OUT.mkdir(parents=True,exist_ok=True);PDF.parent.mkdir(parents=True,exist_ok=True)
DATA=json.loads((REVIEW/'assembly-data.json').read_text())
FPS=DATA['footprints'];BY_REF={f['reference']:f for f in FPS};BOM=DATA['bom']
PAD=DATA['pad_shapes'];GFX=DATA['graphic_shapes']
PAGE_W,PAGE_H=landscape(A3)
FONT='Arial';BOLD='Arial-Bold'
pdfmetrics.registerFont(TTFont(FONT,'C:/Windows/Fonts/arial.ttf'))
pdfmetrics.registerFont(TTFont(BOLD,'C:/Windows/Fonts/arialbd.ttf'))
INK='#163247';MUTED='#586D7D';GOLD='#E5BD63';PIN1='#D34335';GRAY='#ADB7BE'
PALETTE={'C':('#EDF2FF','#506CB0'),'R':('#EAF5E7','#427044'),
         'U':('#DFEEF7','#27597B'),'Y':('#F5E8F3','#8A4D84'),
         'J':('#DEF3EE','#276D60'),'TP':('#DEF3EE','#276D60'),
         'Q':('#FCE8DB','#9B592F'),'D':('#FCE8DB','#9B592F'),
         'F':('#FCE8DB','#9B592F')}
PLACEMENTS={};FAILURES=[]

def color(value):return colors.HexColor(value)
def family(ref):return re.match(r'[A-Z]+',ref)[0]
def ref_key(ref):
    m=re.fullmatch(r'([A-Z]+)(\d+)',ref);return m[1],int(m[2])
def natural(refs):return sorted(refs,key=ref_key)
def short_value(f):
    r=f['reference'];v=f['value']
    if r.startswith('C'):return {'27p':'27pF','100n':'100nF','1u':'1uF','10u':'10uF'}.get(v,v)
    if r.startswith('R'):return v
    if r.startswith('Y'):return '40MHz'
    if r=='F1':return '1A fuse'
    if r=='D2':return '6V8'
    return v
def text(c,x,y,s,size=9,bold=False,fill=INK,align='left'):
    c.setFont(BOLD if bold else FONT,size);c.setFillColor(color(fill))
    getattr(c,{'left':'drawString','center':'drawCentredString','right':'drawRightString'}[align])(x,y,str(s))
def wrap(s,width,size,font=FONT):
    words=str(s).split();lines=[];line=''
    for word in words:
        test=(line+' '+word).strip()
        if pdfmetrics.stringWidth(test,font,size)<=width or not line:line=test
        else:lines.append(line);line=word
    if line:lines.append(line)
    return lines
def para(c,s,x,y,width,size=9,leading=12,bold=False,fill=INK):
    for line in wrap(s,width,size,BOLD if bold else FONT):
        text(c,x,y,line,size,bold,fill);y-=leading
    return y
def header(c,title,subtitle,page):
    text(c,36,PAGE_H-42,title,23,True)
    text(c,36,PAGE_H-61,subtitle,9,False,MUTED)
    c.setStrokeColor(color('#C9D5DC'));c.setLineWidth(.7)
    c.line(36,PAGE_H-72,PAGE_W-36,PAGE_H-72)
    text(c,36,22,'SPI to 8 x CAN FD  |  Assembly guide  |  2026-10-30  |  81 x 80 mm PCB',7,False,MUTED)
    text(c,PAGE_W-36,22,f'{page} / 6',7,False,MUTED,'right')

def body_polygon(f):
    segments=[(g['start'],g['end']) for g in f['graphics'] if g['shape']==GFX['SHAPE_T_SEGMENT']]
    adj=defaultdict(list)
    def key(pt):return tuple(round(v,5) for v in pt)
    for a,b in segments:adj[key(a)].append(key(b));adj[key(b)].append(key(a))
    cycles=[];seen=set()
    for start in adj:
        for second in adj[start]:
            edge=tuple(sorted([start,second]))
            if edge in seen:continue
            chain=[start,second];prev,current=start,second
            for _ in range(100):
                seen.add(tuple(sorted([prev,current])))
                candidates=[pt for pt in adj[current] if pt!=prev]
                if not candidates:break
                nxt=next((p for p in candidates if p==start),None)
                if nxt is None:nxt=next((p for p in candidates if p not in chain),None)
                if nxt is None:break
                if nxt==start:
                    if len(chain)>=3:cycles.append(chain)
                    break
                chain.append(nxt);prev,current=current,nxt
    def area(poly):return abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(poly,poly[1:]+poly[:1])))/2
    if cycles:return max(cycles,key=area)
    rectangles=[g for g in f['graphics'] if g['shape']==GFX['SHAPE_T_RECT']]
    if rectangles:
        g=rectangles[0];a,b=g['start'],g['end'];return [a,[b[0],a[1]],b,[a[0],b[1]]]
    return []

def bbox(points):
    return [min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)]
def center(rect):return [(rect[0]+rect[2])/2,(rect[1]+rect[3])/2]
def expand(rect,n):return [rect[0]-n,rect[1]-n,rect[2]+n,rect[3]+n]
def overlap(a,b):
    return max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
def segment_hits(a,b,rect):
    # Liang-Barsky intersection, for preferring clear callout routes.
    dx,dy=b[0]-a[0],b[1]-a[1];lo,hi=0.,1.
    for pp,qq in [(-dx,a[0]-rect[0]),(dx,rect[2]-a[0]),(-dy,a[1]-rect[1]),(dy,rect[3]-a[1])]:
        if abs(pp)<1e-9:
            if qq<0:return False
        else:
            t=qq/pp
            if pp<0:lo=max(lo,t)
            else:hi=min(hi,t)
            if lo>hi:return False
    return True

def pad_outline(pad):
    w,h=pad['size'];shape=pad['shape']
    if shape==PAD['PAD_SHAPE_CIRCLE']:
        local=[(w/2*math.cos(i*math.tau/48),h/2*math.sin(i*math.tau/48)) for i in range(48)]
    else:
        radius=0
        if shape==PAD['PAD_SHAPE_OVAL']:radius=min(w,h)/2
        elif shape==PAD['PAD_SHAPE_ROUNDRECT']:radius=min(w,h)*pad['roundrect_ratio']
        if radius:
            local=[]
            for cx,cy,start in [(w/2-radius,h/2-radius,0),(-w/2+radius,h/2-radius,90),
                                (-w/2+radius,-h/2+radius,180),(w/2-radius,-h/2+radius,270)]:
                for i in range(9):
                    theta=math.radians(start+i*90/8)
                    local.append((cx+radius*math.cos(theta),cy+radius*math.sin(theta)))
        else:local=[(-w/2,-h/2),(w/2,-h/2),(w/2,h/2),(-w/2,h/2)]
    a=math.radians(-pad['angle']);ca,sa=math.cos(a),math.sin(a);px,py=pad['position']
    return [(px+x*ca-y*sa,py+x*sa+y*ca) for x,y in local]

def draw_polygon(c,points,fill=None,stroke=INK,width=.5,close=True):
    if not points:return
    p=c.beginPath();p.moveTo(*points[0])
    for pt in points[1:]:p.lineTo(*pt)
    if close:p.close()
    c.setLineWidth(width);c.setStrokeColor(color(stroke))
    if fill:c.setFillColor(color(fill))
    c.drawPath(p,stroke=1,fill=int(bool(fill)))

class View:
    def __init__(self,c,side,region,rect,refs=None,detail=False):
        self.c=c;self.side=side;self.region=region;self.rect=rect;self.refs=refs;self.detail=detail
        x0,y0,x1,y1=region;rx,ry,rw,rh=rect
        self.scale=min(rw/(x1-x0),rh/(y1-y0))
        self.x=rx+(rw-(x1-x0)*self.scale)/2
        self.y=ry+(rh-(y1-y0)*self.scale)/2
        self.obstacles=[];self.occupied=[];self.labels={};self.fixed=[]
    def pt(self,p):
        xx,yy=p;x0,y0,x1,y1=self.region
        return [self.x+((xx-x0) if self.side=='front' else (x1-xx))*self.scale,
                self.y+(y1-yy)*self.scale]
    def eligible(self,f):
        return self.refs is None or f['reference'] in self.refs
    def visible(self,pad):return pad[self.side]
    def draw(self,passive_labels=True,all_numbers=False,bare=True):
        c=self.c;x0,y0,x1,y1=self.region
        board_rect=[self.x,self.y,(x1-x0)*self.scale,(y1-y0)*self.scale]
        c.setFillColor(color('#FAFCFC'));c.setStrokeColor(color('#264C5B'));c.setLineWidth(.9)
        c.rect(*board_rect,fill=1,stroke=1)
        bodies=[]
        for f in FPS:
            if not self.eligible(f):continue
            own=f['side']==self.side
            visible=[p for p in f['pads'] if self.visible(p)]
            if not visible:continue
            poly=body_polygon(f)
            if poly and f['purchased']:
                pts=[self.pt(pt) for pt in poly];bb=bbox(pts)
                self.obstacles.append((f['reference'],expand(bb,.7)))
                if own:
                    fill,stroke=PALETTE[family(f['reference'])]
                    draw_polygon(c,pts,fill,stroke,.6)
                else:
                    c.setDash(2,2);draw_polygon(c,pts,None,'#B8C3C9',.5);c.setDash()
                bodies.append((f,bb,own))
            for pad in visible:
                if pad['npth']:
                    xx,yy=self.pt(pad['position']);rr=pad['drill'][0]/2*self.scale
                    c.setFillColor(colors.white);c.setStrokeColor(color('#758894'));c.setLineWidth(.8)
                    c.circle(xx,yy,rr,stroke=1,fill=1)
                    if not self.detail:
                        text(c,xx,yy+rr+3,f['reference'],6,True,MUTED,'center')
                    self.obstacles.append((f['reference'],[xx-rr-1,yy-rr-1,xx+rr+1,yy+rr+1]))
                    continue
                if not f['purchased'] and not bare:continue
                points=[self.pt(pt) for pt in pad_outline(pad)]
                self.obstacles.append((f['reference'],expand(bbox(points),.8)))
                mark=f['purchased'] and family(f['reference']) in ['U','Q','D','Y','J','TP'] and pad['number']=='1'
                fill=PIN1 if mark else GOLD if f['purchased'] else '#C0C9CE'
                draw_polygon(c,points,fill,fill,.25)
                xx,yy=self.pt(pad['position'])
                if pad['drill'][0]:
                    c.setFillColor(colors.white);c.setStrokeColor(color('#687E8D'));c.setLineWidth(.25)
                    c.circle(xx,yy,pad['drill'][0]/2*self.scale,stroke=1,fill=1)
                if all_numbers or mark:
                    # Keep the pad geometry visible; numbers sit just beyond it.
                    fontsize=min(6,max(3.2,self.scale*.42)) if self.detail else 3.1
                    if pad['drill'][0]:
                        text(c,xx,yy-fontsize*.33,pad['number'],fontsize,True,PIN1 if mark else INK,'center')
                    else:
                        sz=pad['size'];points_bb=bbox(points)
                        if self.detail:
                            cy=center([*points_bb])[1]
                            fx,fy=self.pt(f['position'])
                            if abs(xx-fx)>abs(yy-fy):
                                left=xx<fx;tx=points_bb[0]-2 if left else points_bb[2]+2
                                text(c,tx,yy-fontsize*.32,pad['number'],fontsize,True,PIN1 if mark else INK,'right' if left else 'left')
                            else:
                                below=yy<fy;ty=points_bb[1]-fontsize-1 if below else points_bb[3]+2
                                text(c,xx,ty,pad['number'],fontsize,True,PIN1 if mark else INK,'center')
                        elif mark:text(c,xx,yy-1,pad['number'],3,True,'#FFFFFF','center')
                if not f['purchased'] and family(f['reference'])=='TP':
                    text(c,xx,yy-1.5,'TP',3.5,True,'#556773','center')
        # Fabrication outlines include chamfers/notches. Retain exact CAD geometry.
        for f,bb,own in bodies:
            if own:
                for g in f['graphics']:
                    if g['shape']==GFX['SHAPE_T_SEGMENT']:
                        c.setStrokeColor(color(PALETTE[family(f['reference'])][1]));c.setLineWidth(.4)
                        c.line(*self.pt(g['start']),*self.pt(g['end']))
            if f['reference']=='D2' and own:
                pad1=next(p for p in f['pads'] if p['number']=='1')
                pc=self.pt(pad1['position']);bc=center(bb)
                if abs(pc[1]-bc[1])>abs(pc[0]-bc[0]):
                    yy=bb[1]+1.5 if pc[1]<bc[1] else bb[3]-1.5
                    c.setStrokeColor(color(PIN1));c.setLineWidth(2 if not self.detail else 3)
                    c.line(bb[0]+1,yy,bb[2]-1,yy)
                else:
                    xx=bb[0]+1.5 if pc[0]<bc[0] else bb[2]-1.5
                    c.setStrokeColor(color(PIN1));c.setLineWidth(2 if not self.detail else 3)
                    c.line(xx,bb[1]+1,xx,bb[3]-1)
            if not own:
                if not self.detail:
                    ref=f['reference'];xx,yy=center(bb)
                    if ref=='J1':caption='J1 pins - socket on BACK'
                    else:
                        caption=ref+' pins' if ref.startswith('J') else ref
                        if ref in ['J4','J5','J7','J8','J9','J10','J11','J12']:
                            yy=self.pt([f['position'][0],55.2 if ref in ['J4','J5','J7','J8'] else 119.8])[1]
                        elif ref=='J6':
                            pad_x=self.pt(f['pads'][0]['position'])[0]
                            edge=bb[0] if pad_x>center(bb)[0] else bb[2]
                            xx=(edge+pad_x)/2
                    text(c,xx,yy-2,caption,5.1,False,'#6E808C','center')
                continue
            if family(f['reference']) in ['R','C','F']:continue
            ref=f['reference'];xx,yy=center(bb)
            if ref=='J1':
                caption='J1 - FEMALE SOCKET ON BACK'
                text(c,xx,yy-3,caption,9 if not self.detail else 11,True,INK,'center')
            elif ref in ['J4','J5','J7','J8','J9','J10','J11','J12']:
                channel={'J4':1,'J5':2,'J7':3,'J8':4,'J9':5,'J10':6,'J11':7,'J12':8}[ref]
                yy=self.pt([f['position'][0],55.2 if channel<=4 else 119.8])[1]
                text(c,xx,yy-2,f'{ref}  CAN{channel}',7.5 if not self.detail else 9,True,INK,'center')
            elif ref=='J6':
                pad_x=self.pt(f['pads'][0]['position'])[0]
                edge=bb[0] if pad_x>center(bb)[0] else bb[2]
                xx=(edge+pad_x)/2
                text(c,xx,yy-2,'J6',7,True,INK,'center')
            elif ref.startswith('Y'):
                text(c,xx,yy-1.5,ref,4.5 if not self.detail else 8,True,INK,'center')
            elif ref in ['TP13','TP14']:
                text(c,xx,yy-1.8,ref,5.1 if not self.detail else 7,True,INK,'center')
            elif ref in ['Q1','D2','U3']:
                text(c,xx,yy-2,ref,6 if not self.detail else 9,True,INK,'center')
            else:
                second='MCP251863' if ref in [f'U{i}' for i in range(9,17)] else {'U1':'LVC32','U5':'LVC32','U2':'LVC04','U4':'AHC30'}.get(ref,'')
                text(c,xx,yy+3,ref,8 if not self.detail else 10,True,INK,'center')
                text(c,xx,yy-7,second,5.7 if not self.detail else 8,False,INK,'center')
            self.fixed.append(ref)
        if passive_labels:self.place_labels()
        return self
    def place_labels(self):
        c=self.c
        fs=[f for f in FPS if self.eligible(f) and f['purchased'] and f['side']==self.side and family(f['reference']) in ['R','C','F']]
        anchors={f['reference']:center(bbox([self.pt(pt) for p in f['pads'] for pt in pad_outline(p)])) for f in fs}
        def density(f):return sum(math.dist(anchors[f['reference']],pt)<55 for pt in anchors.values())
        fs.sort(key=lambda f:(-density(f),ref_key(f['reference'])))
        bounds=[self.rect[0]-8,self.rect[1]-10,self.rect[0]+self.rect[2]+8,self.rect[1]+self.rect[3]+10]
        for f in fs:
            ref=f['reference'];anchor=anchors[ref]
            own=[b for r,b in self.obstacles if r==ref]
            bb=[min(b[0] for b in own),min(b[1] for b in own),max(b[2] for b in own),max(b[3] for b in own)]
            label=f'{ref} {short_value(f)}';size=5.8 if not self.detail else 8
            width=pdfmetrics.stringWidth(label,BOLD,size)+4;height=size+3.2
            choices=[]
            for gap in [2,5,9,14,21,30,42,58,76]:
                for mode in ['top','bottom','left','right']:
                    for shift in [0,-10,10,-20,20]:
                        if mode in ['top','bottom']:
                            cx=anchor[0]+shift;cy=bb[3]+gap+height/2 if mode=='top' else bb[1]-gap-height/2
                        else:
                            cx=bb[0]-gap-width/2 if mode=='left' else bb[2]+gap+width/2;cy=anchor[1]+shift
                        rect=[cx-width/2,cy-height/2,cx+width/2,cy+height/2]
                        if rect[0]<bounds[0] or rect[1]<bounds[1] or rect[2]>bounds[2] or rect[3]>bounds[3]:continue
                        if any(overlap(expand(rect,.8),b)>0 for _,b in self.obstacles):continue
                        if any(overlap(expand(rect,1),b)>0 for b in self.occupied):continue
                        end=[max(rect[0],min(anchor[0],rect[2])),max(rect[1],min(anchor[1],rect[3]))]
                        crossings=sum(segment_hits(anchor,end,b) for r,b in self.obstacles if r!=ref)
                        score=math.dist(anchor,end)+crossings*25+abs(shift)*.05
                        choices.append((score,rect,end))
                if choices and min(p[0] for p in choices)<45:break
            if not choices:
                FAILURES.append({'side':self.side,'reference':ref});continue
            _,rect,end=min(choices,key=lambda x:x[0]);self.occupied.append(rect);self.labels[ref]=rect
            c.setStrokeColor(color('#526A78'));c.setLineWidth(.45);c.line(*anchor,*end)
            c.setFillColor(color(PALETTE[family(ref)][1]));c.circle(*anchor,.9,fill=1,stroke=0)
            c.setFillColor(colors.white);c.setStrokeColor(color(PALETTE[family(ref)][1]));c.setLineWidth(.3)
            c.roundRect(rect[0],rect[1],rect[2]-rect[0],rect[3]-rect[1],1.5,fill=1,stroke=1)
            text(c,(rect[0]+rect[2])/2,rect[1]+2.1,label,size,True,INK,'center')
        if not self.detail:
            PLACEMENTS[self.side]={'passive_labels':list(self.labels),'fixed_labels':self.fixed,
                                   'all_purchased_refs':natural([f['reference'] for f in FPS if f['purchased'] and f['side']==self.side]),
                                   'label_rectangles':self.labels}

def group_label(row):
    mpn=row['mpn']
    labels={'MCP251863T-E/SS':'CAN IC | SSOP-28','ABM8G-40.000MHZ-18-D2Y-T':'40 MHz crystal | 3.2 x 2.5 mm',
      'TLV75533PDBVR':'3.3 V LDO | SOT-23-5','CL10C270JB8NNNC':'27 pF | 0603',
      'CC0603KRX7R9BB104':'100 nF | 0603','CGA3E1X7R1E105K080AC':'1 uF | 0603',
      'CL21B106KOQNNNE':'10 uF | 0805','RC1206FR-07120RL':'120 ohm | 1206',
      'AC0603FR-0710KL':'10 kohm | 0603','CRCW0603100KFKEA':'100 kohm | 0603',
      'RC0603FR-0733RL':'33 ohm | 0603','B3B-XH-A':'CAN connector | 3-pin XH',
      'B2B-XH-A':'5 V input | 2-pin XH','M20-7832046':'Jetson socket | FEMALE 2 x 20',
      '0466001.NR':'1 A fuse | 1206','AO3401A':'P-channel MOSFET | SOT-23',
      'BZT52C6V8-13-F':'6.8 V Zener | SOD-123','74AHC30PW,118':'NAND | TSSOP-14',
      '74LVC32APW,118':'OR | TSSOP-14','74LVC04AT14-13':'Inverter | TSSOP-14',
      'M20-9990246':'Test header | 1 x 2'}
    return labels[mpn]

def side_key(c,side,x,y,width):
    text(c,x,y,'FIT THESE PARTS ON THIS FACE',11,True);y-=20
    grouped=[]
    for row in BOM:
        refs=natural([r for r in row['placed_references'].split(';') if BY_REF[r]['side']==side])
        if refs:grouped.append((row,refs))
    for row,refs in grouped:
        fill,stroke=PALETTE[family(refs[0])]
        c.setFillColor(color(fill));c.setStrokeColor(color(stroke));c.setLineWidth(.5)
        c.roundRect(x,y-6,8,8,2,fill=1,stroke=1)
        text(c,x+14,y,group_label(row)+f'  x{len(refs)}',8.7,True)
        text(c,x+14,y-11,row['mpn'],7.8,False,MUTED)
        ref_lines=wrap(', '.join(refs),width-16,6.7)
        yy=y-20
        for line in ref_lines:text(c,x+14,yy,line,6.7);yy-=8
        y=yy-4
    return y

def map_page(c,side,page):
    title='FRONT - look directly at the component face' if side=='front' else 'BACK - board flipped left to right'
    cnt=Counter(f['side'] for f in FPS if f['purchased'])[side]
    subtitle=f'{cnt} components mounted on this face. Leaders point to exact footprints. Match each reference and value to the parts key.'
    header(c,title,subtitle,page)
    view=View(c,side,DATA['board_bounds_mm'],[38,66,680,672]).draw()
    key_x=756;key_width=PAGE_W-key_x-36
    y=side_key(c,side,key_x,PAGE_H-96,key_width)
    if side=='front':
        y-=4
        text(c,key_x,y,'READ THE PADS',9,True);y-=14
        y=para(c,'Red pad = pin 1. D2 red end = cathode band. R, C and F1 have no polarity.',key_x,y,key_width,8.3,11)
        y-=7
        y=para(c,'Dashed J1 outline: pins only. The FEMALE socket body mounts on the BACK, and its pins are soldered from this front face.',key_x,y,key_width,8.3,11)
    else:
        y-=12
        text(c,key_x,y,'J1 IS THE BACK-MOUNTED SOCKET',12,True);y-=19
        y=para(c,'Fit the female M20-7832046 socket from this face. Its 40 legs protrude onto the front, where you solder them. Do not install J1 on the front.',key_x,y,key_width,10,14)
        y-=14
        y=para(c,'In this back view, pin 1 is at the LEFT end of the UPPER row. Odd pins run left to right along the upper row; even pins run along the lower row.',key_x,y,key_width,9,13)
        y-=18
        text(c,key_x,y,'OTHER THROUGH-HOLES ON THIS VIEW',10,True);y-=17
        y=para(c,'Dashed JST and TP13/TP14 outlines are the solder-pad side of FRONT-mounted connectors. Their plastic bodies belong on the other face.',key_x,y,key_width,9,13)
        y-=18
        text(c,key_x,y,'100K AND 10K ARE DIFFERENT PARTS',10,True);y-=17
        y=para(c,'R34/R35/R36/R37: 100 kohm Vishay CRCW0603100KFKEA. R7/R8/R11/R14/R17/R24/R27/R30: 10 kohm YAGEO AC0603FR-0710KL. R38 is the remaining 10 kohm resistor, on the FRONT.',key_x,y,key_width,9,13)
    y=min(y-15,105)
    bottom=para(c,'Gray TP pads need no component. H1-H4 are mounting holes. Traces and vias are omitted for assembly clarity. Package outlines show the body position, not a photograph.',key_x,y,key_width,7.6,10,fill=MUTED)
    assert bottom>35,('Sidebar overflow',side,bottom)
    text(c,38,44,'Board top stays at the top on both views. Back view is mirrored horizontally. Zoom or print on A3; the drawing is enlarged, not 1:1.',7.6,False,MUTED)
    c.showPage()

def panel(c,x,y,w,h,title,subtitle,refs,side='front',numbers=True):
    c.setFillColor(colors.white);c.setStrokeColor(color('#CEDAE0'));c.setLineWidth(.7)
    c.roundRect(x,y,w,h,5,fill=1,stroke=1)
    text(c,x+14,y+h-23,title,12,True)
    yy=para(c,subtitle,x+14,y+h-39,w-28,8.4,11)
    pts=[pt for r in refs for p in BY_REF[r]['pads'] for pt in pad_outline(p)]
    pts += [pt for r in refs for pt in body_polygon(BY_REF[r])]
    region=bbox(pts);region=expand(region,.8)
    usable=[x+24,y+18,w-48,max(50,yy-y-30)]
    v=View(c,side,region,usable,refs=set(refs),detail=True).draw(passive_labels=False,all_numbers=numbers,bare=False)
    return v

def orientation_page(c):
    header(c,'Orientation checks before soldering','Every close-up retains the exact rotation of the footprint in the saved board. Red pad = pin 1.',3)
    gap=18;w=(PAGE_W-72-2*gap)/3;h=322;top=PAGE_H-90-h
    entries=[
      ('U9 - U12: upper CAN ICs','Example U9. Match the package pin-1 dot / chamfer to the red pad. Do not use the direction of the printed part name.', ['U9']),
      ('U13 - U16: lower CAN ICs','Example U13. These ICs are rotated 180 degrees relative to the upper group. Pin 1 moves to the opposite corner.', ['U13']),
      ('U1/U2 vs U5/U4: logic ICs','U1 and U2 share one orientation; U5 and U4 face the other way. Compare U1 (left) with U5 (right).', ['U1','U5']),
      ('U3 - 3.3 V regulator','TLV75533PDBVR, SOT-23-5. Pin 1 = protected 5 V; pin 2 = GND; pin 3 = enable/5 V; pin 4 = NC; pin 5 = 3.3 V.', ['U3']),
      ('Q1 and D2 - power protection','Q1: pin 1 gate, 2 source, 3 drain. D2: pad 1 is CATHODE (K). Its band faces the lower board edge in this front view.', ['Q1','D2']),
      ('Y1 - Y8: four-pad crystals','Example Y1. Pins 1 and 3 are crystal terminals; 2 and 4 are GND. Keep the long axis as drawn. A 180-degree turn preserves this pattern; a 90-degree turn does not.', ['Y1'])]
    for i,(title,desc,refs) in enumerate(entries):
        x=36+(i%3)*(w+gap);y=top if i<3 else top-h-gap
        panel(c,x,y,w,h,title,desc,refs)
    c.showPage()

def connector_page(c):
    header(c,'Connector placement and first voltage checks','Front and back are physical viewing directions. Red through-hole pad marks pin 1.',4)
    # Long socket drawing is deliberately shown from its mounting face.
    panel(c,36,PAGE_H-340,PAGE_W-72,245,'J1 - FEMALE socket mounted on the BACK',
          'Back view, enlarged. Pin 1 is the upper-left red pad. Fit the socket from the back; solder its legs from the front. The opposite (front) view reverses left and right.', ['J1'],side='back')
    w=(PAGE_W-108)/3;y=100;h=370
    panel(c,36,y,w,h,'J4/J5/J7/J8/J9/J10/J11/J12',
          'All CAN JST connectors mount on the FRONT. Example J4: pin 1 CANH; pin 2 CANL; pin 3 GND. Match the plastic housing to the outline; the connector at the other board edge is rotated.', ['J4'])
    panel(c,54+w,y,w,h,'J6 - external 5 V input, FRONT',
          'B2B-XH-A. Pin 1 = GND. Pin 2 = +5 V input BEFORE the fuse and reverse-polarity MOSFET. Confirm cable polarity against pad numbers, not wire colors.', ['J6'])
    panel(c,72+2*w,y,w,h,'TP13 and TP14 - test headers, FRONT',
          'TP13: pin 1 = 3.3 V (VDD_VIO), pin 2 = GND. TP14: pin 1 = protected 5 V (VCC), pin 2 = GND. Fit M20-9990246 headers at these two locations only.', ['TP13','TP14'])
    text(c,36,66,'First power-up: Jetson and CAN cables disconnected. Use a current-limited 5 V supply at J6; measure TP14 then TP13 before connecting a host.',10,True)
    text(c,36,48,'Bare TP1-TP12 and TP15-TP23 are probe pads. No header or other purchased part is fitted there.',8.5,False,MUTED)
    c.showPage()

def parts_page(c):
    header(c,'Fitted parts key - use these exact purchased parts','120 fitted packages, 21 purchase types. Spare parts in the order list are not additional PCB placements.',5)
    cols=[36,190,250,307,600,1154]
    top=PAGE_H-98;head_h=25
    c.setFillColor(color('#173D53'));c.rect(36,top-head_h,PAGE_W-72,head_h,fill=1,stroke=0)
    for x,label in zip([43,198,258,315,608],['Value / role','Front','Back','References','Manufacturer part to fit']):
        text(c,x,top-16,label,9,True,'#FFFFFF')
    y=top-head_h
    for i,row in enumerate(BOM):
        refs=natural(row['placed_references'].split(';'));sides=Counter(BY_REF[r]['side'] for r in refs)
        reference_lines=wrap(', '.join(refs),cols[4]-cols[3]-18,8)
        role_lines=wrap(group_label(row),cols[1]-cols[0]-15,8)
        rh=max(27,max(len(reference_lines),len(role_lines))*11+12)
        if i%2:
            c.setFillColor(color('#F0F5F7'));c.rect(36,y-rh,PAGE_W-72,rh,fill=1,stroke=0)
        yy=y-15
        for line in role_lines:text(c,43,yy,line,8,True);yy-=11
        text(c,216,y-15,sides.get('front',0),9,False,INK,'center')
        text(c,270,y-15,sides.get('back',0),9,False,INK,'center')
        yy=y-15
        for line in reference_lines:text(c,315,yy,line,8);yy-=11
        text(c,608,y-15,row['mpn'],9,True)
        if row['mpn']!=row['cad_mpn']:
            text(c,608,y-26,'Approved purchase substitute for '+row['cad_mpn'],7,False,MUTED)
        y-=rh
    assert y>80,('Parts table overflow',y)
    y-=18
    text(c,36,y,'No component is fitted on the 21 bare test pads or on H1-H4. All MLCC capacitors, resistors and F1 are non-polarized.',9,True)
    text(c,36,y-17,'Keep the 27 pF and 100 nF capacitors separated on the bench; many ceramic capacitors have no readable value marking.',9)
    c.showPage()

def step(c,num,title,body,x,y,width):
    text(c,x,y,f'{num:02d}',14,True,'#267265');text(c,x+31,y+1,title,12,True)
    yy=para(c,body,x+31,y-17,width-31,9.5,13)
    return yy-19

def method_page(c):
    header(c,'How to solder this board','A practical sequence for this particular double-sided, four-layer PCB.',6)
    gap=38;colw=(PAGE_W-72-gap)/2;x1=36;x2=36+colw+gap;y=PAGE_H-105
    y=step(c,1,'Prepare parts and tools',
      'Use magnification, fine tweezers, a temperature-controlled iron, electronics flux, fine solder wire, solder wick and fume extraction. A stencil plus paste and controlled reflow, or suitable hot-air equipment, helps with the small packages and the crystal terminals underneath the bodies. Sort each value into a labeled tray; use the fitted parts key, including the approved 10k and 100k replacements.',x1,y,colw)
    y=step(c,2,'Assemble BACK SMD parts first',
      'Fit the 28 back-side resistors. All eight 120-ohm terminations are the larger 1206 size; the 33-ohm, 10k and 100k resistors are 0603. With an iron, lightly tin one pad, hold the part flat, reflow that end, then solder the other end. Use enough heat to wet both pad and termination without prolonged contact. Leave J1 off until the small parts are finished.',x1,y,colw)
    y=step(c,3,'Assemble FRONT SMD parts',
      'Fit the 80 front-side SMD parts, checking orientation before soldering. For SSOP/TSSOP ICs, align every lead over its own pad, tack two opposite corner leads, recheck alignment, then use flux and a small solder amount to finish the pins. Remove bridges with flux and wick; inspect the heel and toe of each joint. The four-pad Y1-Y8 crystals benefit from solder paste and controlled reflow so their underside terminals actually wet.',x1,y,colw)
    y=step(c,4,'Handle double-sided heating carefully',
      'Support the PCB at its edges so already-fitted parts are not crushed. If reflowing both sides, use a process and fixture appropriate to double-sided assembly; previously soldered parts can remelt or move. Fit tall through-hole plastic connectors after the SMD reflow steps. Follow the paste and component manufacturers\' profiles rather than choosing a universal hot-air or oven temperature.',x1,y,colw)
    y=step(c,5,'Fit the through-hole connectors last',
      'J4/J5/J7/J8/J9/J10/J11/J12, J6 and TP13/TP14 mount from the FRONT and are soldered from the BACK. J1 is the FEMALE 40-pin socket: fit it from the BACK and solder all 40 legs from the FRONT. Tack one pin, confirm the housing sits square and flush, then finish the remaining joints. Heat the lead and copper together and feed solder into the joint.',x1,y,colw)
    y2=PAGE_H-105
    y2=step(c,6,'Inspect every placement before power',
      'Check the value at every reference. Pay particular attention to 27 pF versus 100 nF, 10k versus 100k, and F1 versus a resistor. Match every IC pin-1 indicator to the red pad on the map. D2\'s cathode band points toward its pad 1. Q1 uses gate 1 / source 2 / drain 3. Check that no lead sits between pads, no resistor or capacitor is standing on one end, and no pin-to-pin solder bridge remains.',x2,y2,colw)
    y2=step(c,7,'Clean and check with a meter',
      'Remove flux residues using the flux manufacturer\'s recommended method. With all power and cables removed, check for unintended shorts from each supply rail to GND and between neighboring fine-pitch pins. Capacitors can briefly charge during resistance checks; a short beep alone is not a complete diagnosis. F1 is supposed to show continuity. Do not intentionally fill vias, bare test pads or mounting holes with solder.',x2,y2,colw)
    y2=step(c,8,'Bring up the power rails first',
      'Keep the Jetson and all CAN cables disconnected. Feed a current-limited regulated 5 V supply into J6 pin 2, with GND on J6 pin 1. Check protected 5 V at TP14 pin 1 relative to pin 2, then approximately 3.3 V at TP13 pin 1 relative to pin 2. If the supply current-limits, a part heats unexpectedly or a rail is wrong, remove power and investigate before connecting the host. The existing design still needs system timing, power-sequence and thermal validation.',x2,y2,colw)
    y2-=2;text(c,x2,y2,'Sources and drawing basis',11,True);y2-=17
    sources=[('MCP251863 pinout / package marking','https://ww1.microchip.com/downloads/aemDocuments/documents/APID/ProductDocuments/DataSheets/MCP251863-Data-Sheet-DS20006624A.pdf'),
             ('Abracon ABM8G four-pad crystal','https://abracon.com/Resonators/ABM8G.pdf'),
             ('AO3401A pin assignment','https://www.aosmd.com/sites/default/files/res/datasheets/AO3401A.pdf'),
             ('TI TLV755 regulator pinout','https://www.ti.com/lit/ds/symlink/tlv755p.pdf'),
             ('Kester soldering and flux process guidance','https://www.kester.com/knowledge-base/faq')]
    for label,url in sources:
        text(c,x2,y2,label,8,False,'#1E668E');c.linkURL(url,(x2,y2-2,x2+colw,y2+9),relative=0);y2-=15
    y2-=6
    y2=para(c,'Geometry and reference positions were extracted directly from the saved KiCad PCB. This guide uses the current fitted BOM, including AC0603FR-0710KL and CRCW0603100KFKEA. Neither CAD nor fabrication files were changed.',x2,y2,colw,8,11,fill=MUTED)
    text(c,x2,y2-13,'PCB SHA-256: '+DATA['input_sha256']['breakout/breakout.kicad_pcb'][:24]+'...',7,False,MUTED)
    assert min(y,y2)>45,('Method content overflow',y,y2)
    c.showPage()

def main():
    for name,digest in DATA['input_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    c=canvas.Canvas(str(PDF),pagesize=(PAGE_W,PAGE_H),pageCompression=1)
    c.setTitle('PCB assembly maps and soldering guide - SPI to 8 x CAN FD')
    c.setAuthor('Assembly documentation')
    map_page(c,'front',1);map_page(c,'back',2)
    orientation_page(c);connector_page(c);parts_page(c);method_page(c)
    assert not FAILURES,FAILURES
    for side in ['front','back']:
        placed=PLACEMENTS[side]
        assert set(placed['passive_labels'])|set(placed['fixed_labels'])==set(placed['all_purchased_refs'])
        boxes=list(placed['label_rectangles'].values())
        assert not any(overlap(a,b)>0 for i,a in enumerate(boxes) for b in boxes[i+1:])
    c.save()
    for name,digest in DATA['input_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    (REVIEW/'placement-validation.json').write_text(json.dumps({'purchased_labels':120,
        'front':91,'back':29,'front_smd':80,'back_smd':28,'front_through_hole':11,'back_through_hole':1,
        'missing_labels':FAILURES,'overlapping_passive_label_boxes':0,'back_view_mirrored':True,
        'j1_mounting_side':'back','bare_test_pads':21,'mounting_holes':4,
        'sources_unchanged':True,'placements':PLACEMENTS},indent=2)+'\n')
    print(json.dumps({'pdf':str(PDF),'pages':6,'front_components':91,'back_components':29,'source_CAD_unchanged':True}))

if __name__=='__main__':main()
