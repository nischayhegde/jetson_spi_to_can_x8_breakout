"""Read saved PCB geometry and approved fitted BOM without changing CAD."""
from pathlib import Path
from collections import Counter
import csv, hashlib, json
import pcbnew as p

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
board=p.LoadBoard(str(ROOT/'breakout/breakout.kicad_pcb'))
bom=list(csv.DictReader((ROOT/'componentlist.csv').open(encoding='utf-8-sig')))
by_ref={ref:row for row in bom for ref in row['placed_references'].split(';')}
assert len(by_ref)==120
def xy(v):return [p.ToMM(v.x),p.ToMM(v.y)]
fps=[]
for fp in board.GetFootprints():
    ref=fp.GetReference()
    pads=[]
    for pad in fp.Pads():
        pads.append({'number':pad.GetNumber(),'position':xy(pad.GetPosition()),
                     'size':xy(pad.GetSize()),'drill':xy(pad.GetDrillSize()),
                     'angle':pad.GetOrientationDegrees(),'shape':int(pad.GetShape()),
                     'shape_name':str(pad.GetShape()),'roundrect_ratio':pad.GetRoundRectRadiusRatio(),
                     'npth':pad.GetAttribute()==p.PAD_ATTRIB_NPTH,
                     'front':pad.IsOnLayer(p.F_Cu),'back':pad.IsOnLayer(p.B_Cu),
                     'net':pad.GetNetname()})
    graphics=[]
    for g in fp.GraphicalItems():
        if isinstance(g,p.PCB_SHAPE) and g.GetLayer() in [p.F_Fab,p.B_Fab]:
            item={'shape':int(g.GetShape()),'start':xy(g.GetStart()),'end':xy(g.GetEnd()),
                  'width':p.ToMM(g.GetWidth()),'layer':board.GetLayerName(g.GetLayer())}
            if g.GetShape() in [p.SHAPE_T_CIRCLE,p.SHAPE_T_ARC]:
                item['center']=xy(g.GetCenter())
                if g.GetShape()==p.SHAPE_T_ARC:item['mid']=xy(g.GetArcMid())
            if g.GetShape()==p.SHAPE_T_POLY:
                item['polygon']=[xy(v) for v in g.GetPolyPoints()]
            graphics.append(item)
    row=by_ref.get(ref)
    fp_record={'reference':ref,'value':fp.GetValue(),'position':xy(fp.GetPosition()),
               'side':'front' if fp.GetLayer()==p.F_Cu else 'back',
               'angle':fp.GetOrientationDegrees(),'footprint':fp.GetFPID().GetUniStringLibId(),
               'pads':pads,'graphics':graphics,'purchased':row is not None,
               'mpn':row['mpn'] if row else None,'cad_mpn':row['cad_mpn'] if row else None,
               'manufacturer':row['manufacturer'] if row else None,
               'function':row['function'] if row else None}
    if row:
        assert row['cad_mpn']==fp.GetFieldText('MPN'),ref
        assert row['footprint']==fp_record['footprint'],ref
    fps.append(fp_record)
edges=[{'start':xy(g.GetStart()),'end':xy(g.GetEnd()),'shape':int(g.GetShape())}
       for g in board.GetDrawings() if g.GetLayer()==p.Edge_Cuts]
data={'date':'2026-10-30','board_bounds_mm':[56,47.5,137,127.5],'footprints':fps,
      'bom':bom,'edges':edges,'pad_shapes':{n:int(getattr(p,n)) for n in
        ['PAD_SHAPE_CIRCLE','PAD_SHAPE_OVAL','PAD_SHAPE_RECT','PAD_SHAPE_ROUNDRECT','PAD_SHAPE_TRAPEZOID','PAD_SHAPE_CUSTOM']},
      'graphic_shapes':{n:int(getattr(p,n)) for n in
        ['SHAPE_T_SEGMENT','SHAPE_T_RECT','SHAPE_T_ARC','SHAPE_T_CIRCLE','SHAPE_T_POLY']},
      'input_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
        ['breakout/breakout.kicad_pcb','breakout/breakout.kicad_sch','componentlist.csv','purchasing_config.json']}}
(OUT/'assembly-data.json').write_text(json.dumps(data,indent=2)+'\n')
print('Purchased packages by mounting side:',dict(Counter(f['side'] for f in fps if f['purchased'])))
print('Pad shapes:',dict(Counter(pad['shape'] for f in fps for pad in f['pads'])))
for fp in sorted(fps,key=lambda f:(f['side'],f['position'][1],f['position'][0])):
    if fp['purchased']:
        print(fp['reference'],fp['side'],fp['position'],fp['angle'],fp['value'],fp['mpn'])
