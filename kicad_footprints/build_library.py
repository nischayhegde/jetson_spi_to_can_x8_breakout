"""Bundle selected parts from installed official KiCad 10 libraries.

Run with ordinary Python. No network calls; no changes to the existing design.
"""
from pathlib import Path
import csv
import hashlib
import json
import re
import shutil
from library_usage import active_selection

ROOT = Path(__file__).resolve().parent
KICAD = Path(r'C:\Program Files\KiCad\10.0\share\kicad')
LIB = 'BreakoutBoard'
FP = ROOT / (LIB + '.pretty')
MODELS = ROOT / '3dmodels'
FP.mkdir(exist_ok=True)
MODELS.mkdir(exist_ok=True)

def dk(maker, mpn, ident):
    return f'https://www.digikey.com/en/products/detail/{maker}/{mpn}/{ident}'

# MPN, quantity, function, source symbol, source footprint, supplier URL,
# observed stock (web/index snapshots, not a reservation), single-unit USD if known.
parts = [
 ('MCP251863T-E_SS',8,'Integrated SPI CAN FD controller/transceiver','Interface_CAN_LIN:MCP251863T-H-SS','Package_SO:SSOP-28_5.3x10.2mm_P0.65mm',dk('microchip-technology','MCP251863T-E-SS',15985723),820,2.30),
 ('ABM8G-40.000MHZ-18-D2Y-T',8,'40 MHz passive crystal, CL=18 pF','Device:Crystal_GND24','Crystal:Crystal_SMD_Abracon_ABM8G-4Pin_3.2x2.5mm','https://www.mouser.com/en/ProductDetail/ABRACON/ABM8G-40.000MHZ-18-D2Y-T?qs=3LVMET7lfiO1sAQRIVmcWA%3D%3D',1362,None),
 ('ESDONCAN1LT1G',8,'Dual bidirectional CAN TVS','Power_Protection:NUP2105L','Package_TO_SOT_SMD:SOT-23','https://www.mouser.com/en/ProductDetail/onsemi/ESDONCAN1LT1G?qs=xGcJQ%252BnsJwvlHkj2cpk%252Btw%3D%3D',7124,.55),
 ('ISO7763DWR',4,'Six-channel digital isolator, 3 forward/3 reverse','Isolator:ISO7763DW','Package_SO:SOIC-16W_7.5x10.3mm_P1.27mm','https://www.mouser.com/en/ProductDetail/Texas-Instruments/ISO7763DWR?qs=BZBei1rCqCCY2ZEA%252BvwxBA%3D%3D',358,None),
 ('TMR_6-0511',1,'Regulated isolated 5 V / 1.2 A, 6 W converter',None,'Converter_DCDC:Converter_DCDC_TRACO_TMR-xxxx_THT',dk('traco-power','TMR-6-0511',9383425),1085,24.18),
 ('TPS259530DSGR',1,'Input eFuse, latch-off, adjustable current limit',None,'Package_SON:WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm',dk('texas-instruments','TPS259530DSGR',8038175),6664,1.04),
 ('TLV75533PDBVR',1,'Host-side 3.3 V LDO','Regulator_Linear:TLV75533PDBV','Package_TO_SOT_SMD:SOT-23-5',dk('texas-instruments','TLV75533PDBVR',9356541),84540,.45),
 ('CL10C270JB8NNNC',16,'27 pF 50 V C0G +/-5% crystal load capacitor, 0603','Device:C','Capacitor_SMD:C_0603_1608Metric',dk('samsung-electro-mechanics','CL10C270JB8NNNC',3889172),1471,.10),
 ('CC0603KRX7R9BB104',34,'100 nF 50 V X7R bypass capacitor','Device:C','Capacitor_SMD:C_0603_1608Metric',dk('yageo','CC0603KRX7R9BB104',2103082),21441,.14),
 ('CGA3E1X7R1E105K080AC',20,'1 uF 25 V X7R local and LDO capacitor','Device:C','Capacitor_SMD:C_0603_1608Metric',dk('tdk-corporation','CGA3E1X7R1E105K080AC',2672824),1048821,None),
 ('CL21B106KOQNNNE',4,'10 uF 16 V X7R power bulk capacitor','Device:C','Capacitor_SMD:C_0805_2012Metric',dk('samsung-electro-mechanics','CL21B106KOQNNNE',3890958),322235,None),
 ('CC0603KRX7R9BB103',1,'10 nF 50 V X7R eFuse slew capacitor','Device:C','Capacitor_SMD:C_0603_1608Metric',dk('yageo','CC0603KRX7R9BB103',302995),635615,None),
 ('RC1206FR-07120RL',8,'120 ohm 1% 0.25 W selectable CAN termination','Device:R','Resistor_SMD:R_1206_3216Metric',dk('yageo','RC1206FR-07120RL',728523),65122,.10),
 ('RC0603FR-0710KL',26,'10 kohm 1% bias and reverse-protection gate pull-down','Device:R','Resistor_SMD:R_0603_1608Metric','https://www.mouser.com/en/ProductDetail/YAGEO/RC0603FR-0710KL?qs=grNVn54RoB%252B3GtjbJj3wJQ%3D%3D',1640807,.10),
 ('RC0603FR-07100KL',4,'100 kohm 1% native-CS startup pull-up, 0603','Device:R','Resistor_SMD:R_0603_1608Metric',dk('yageo','RC0603FR-07100KL',729836),2081355,.10),
 ('RC0603FR-0733RL',14,'33 ohm 1% SPI source damping','Device:R','Resistor_SMD:R_0603_1608Metric','https://www.mouser.com/en/ProductDetail/YAGEO/RC0603FR-0733RL?qs=diQw95jMAeMotgif2GSHTQ%3D%3D',595649,.10),
 ('CRCW06031K21FKEA',1,'1.21 kohm 1% eFuse ILM setting','Device:R','Resistor_SMD:R_0603_1608Metric',dk('vishay-dale','CRCW06031K21FKEA',1179818),49852,.10),
 ('B3B-XH-A',8,'3-pin 2.50 mm CAN connector','Connector_Generic:Conn_01x03','Connector_JST:JST_XH_B3B-XH-A_1x03_P2.50mm_Vertical',dk('jst-sales-america-inc','B3B-XH-A',1651046),69190,.13),
 ('B2B-XH-A',1,'2-pin 2.50 mm 5 V input connector','Connector_Generic:Conn_01x02','Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical',dk('jst-sales-america-inc','B2B-XH-A',1651045),304650,None),
 ('M20-7832046',1,'40-pin female socket, 2 x 20, 2.54 mm pitch, vertical through-hole','Connector_Generic:Conn_02x20_Odd_Even','Connector_PinSocket_2.54mm:PinSocket_2x20_P2.54mm_Vertical',dk('harwin-inc','M20-7832046',3728114),4597,4.34),
 ('M20-9990246',2,'Two-pin 2.54 mm vertical through-hole test header','Connector:TestPoint_2Pole','Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical',dk('harwin-inc','M20-9990246',3728226),179951,.10),
 ('0466001.NR',1,'1 A 63 V fast-acting series input fuse, 1206; V1 load qualification required','Device:Fuse','Fuse:Fuse_1206_3216Metric',dk('littelfuse-inc','0466001-NR',521337),36047,1.25),
 ('AO3401A',1,'P-channel -30 V MOSFET for 5 V high-side reverse-hookup protection','Transistor_FET:AO3401A','Package_TO_SOT_SMD:SOT-23',dk('alpha-omega-semiconductor-inc','AO3401A',1855943),358299,.52),
 ('BZT52C6V8-13-F',1,'6.8 V gate-source Zener clamp, SOD123; not a supply-rail clamp','Device:D_Zener','Diode_SMD:D_SOD-123',dk('diodes-incorporated','BZT52C6V8-13-F',4570599),6702,.22),
 ('74LVC08APW,118',2,'Quad 2-input AND, 3.3 V host-side CS bank logic','74xx:74LS08','Package_SO:TSSOP-14_4.4x5mm_P0.65mm',dk('nexperia-usa-inc','74LVC08APW-118',2209917),17941,.23),
 ('74AHC30PW,118',1,'8-input NAND plus spare NOT implements shared-IRQ AND','74xx:74LS30','Package_SO:TSSOP-14_4.4x5mm_P0.65mm','https://www.mouser.com/ProductDetail/Nexperia/74AHC30PW118?qs=P62ublwmbi%252B963Q4ACANGA%3D%3D',3795,.39),
 ('74LVC32APW,118',1,'Quad 2-input OR, 3.3 V host-side logic provision','74xx:74LS32','Package_SO:TSSOP-14_4.4x5mm_P0.65mm',dk('nexperia-usa-inc','74LVC32APW-118',946666),6092,.25),
 ('74LVC04AT14-13',3,'Hex inverter, 3.3 V host-side CS bank logic','74xx:74LS04','Package_SO:TSSOP-14_4.4x5mm_P0.65mm',dk('diodes-incorporated','74LVC04AT14-13',10452774),3994,.32),
]

# Generate only the current schematic's selected parts. Generic C/R symbols
# retain their mapped packages; quantities count unique placed references.
# Quantities come only from placed parts, including the fitted F1 fuse.
selection = active_selection({row[0] for row in parts})
parts=[(n,selection[n]['quantity'],d,s,f,u,st,p)
       for n,q,d,s,f,u,st,p in parts if n in selection]

def block(text, start):
    depth, quoted, escaped = 0, False, False
    for i in range(start,len(text)):
        c=text[i]
        if escaped:
            escaped=False
        elif c=='\\' and quoted:
            escaped=True
        elif c=='"':
            quoted=not quoted
        elif not quoted:
            if c=='(': depth+=1
            elif c==')':
                depth-=1
                if depth==0: return text[start:i+1]
    raise ValueError('Unbalanced expression')

def rename_symbol(text, old, new):
    # Rename the symbol and its drawing units, not arbitrary text. Replacing
    # every "C" or "R" also changed passive reference prefixes into full MPNs.
    return re.sub(r'(\(symbol ")'+re.escape(old)+r'(?="|_\d+_\d+")',
                  lambda m:m[1]+new,text)

def symbol(source):
    lib,name=source.split(':')
    text=(KICAD/'symbols'/f'{lib}.kicad_sym').read_text(encoding='utf-8')
    b=block(text,text.index(f'(symbol "{name}"'))
    parent=re.search(r'\(extends "([^"]+)"\)',b)
    if parent:
        base=symbol(lib+':'+parent[1])
        for p in re.finditer(r'\(property "([^"]+)"',b):
            prop=block(b,p.start())
            existing=re.search(r'\(property "'+re.escape(p[1])+r'"',base)
            if existing:
                old=block(base,existing.start())
                base=base.replace(old,prop,1)
            else: base=base[:-1]+prop+'\n)'
        base=rename_symbol(base,parent[1],name)
        return base
    return b

def custom(name,pins):
    s=f'''(symbol "{name}" (in_bom yes) (on_board yes)
      (property "Reference" "U" (at 0 13 0) (effects (font (size 1.27 1.27))))
      (property "Value" "{name}" (at 0 11 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
      (symbol "{name}_0_1" (rectangle (start -7.62 10.16) (end 7.62 -10.16)
        (stroke (width 0.254) (type default)) (fill (type background))))
      (symbol "{name}_1_1"'''
    for n,label,kind,x,y,angle in pins:
        s+=f'''(pin {kind} line (at {x} {y} {angle}) (length 2.54)
          (name "{label}" (effects (font (size 1 1))))
          (number "{n}" (effects (font (size 1 1)))))'''
    return s+'))'

customs={
 'TPS259530DSGR':custom('TPS259530DSGR',[
  ('1','dVdt','passive',-10.16,0,0),('2','EN/UVLO','input',-10.16,2.54,0),
  ('3','IN','power_in',-10.16,7.62,0),('4','IN','power_in',-10.16,5.08,0),
  ('5','OUT','power_out',10.16,7.62,180),('6','~{FLT}','open_collector',10.16,2.54,180),
  ('7','ILM','passive',10.16,-2.54,180),('8','GND','power_in',-2.54,-12.7,90),
  ('9','GND_PAD','power_in',2.54,-12.7,90)]),
 'TMR_6-0511':custom('TMR_6-0511',[
  ('1','-VIN','power_in',-10.16,-5.08,0),('2','+VIN','power_in',-10.16,5.08,0),
  ('3','REMOTE','input',-10.16,0,0),('5','NC','no_connect',10.16,7.62,180),
  ('6','+VOUT','power_out',10.16,5.08,180),('7','-VOUT','power_out',10.16,-5.08,180),
  ('8','NC','no_connect',10.16,-7.62,180)])}

symbols=[]
manifest=[]
for name,qty,desc,src,fp,url,stock,price in parts:
    oldlib,oldfp=fp.split(':')
    path=KICAD/'footprints'/f'{oldlib}.pretty'/f'{oldfp}.kicad_mod'
    data=path.read_text(encoding='utf-8')
    refs=re.findall(r'\(model "([^"]+)"',data)
    local_models=[]
    for ref in refs:
        relative=re.sub(r'^\$\{[^}]+\}/','',ref)
        step=KICAD/'3dmodels'/Path(relative).with_suffix('.step')
        if not step.exists(): raise FileNotFoundError(step)
        dest=MODELS/step.name
        shutil.copy2(step,dest)
        data=data.replace(ref,'${KIPRJMOD}/../kicad_footprints/3dmodels/'+step.name)
        local_models.append('3dmodels/'+step.name)
    if not refs: raise ValueError('No model for '+fp)
    (FP/(oldfp+'.kicad_mod')).write_text(data,encoding='utf-8')
    b=symbol(src) if src else customs[name]
    oldname=re.match(r'\(symbol "([^"]+)"',b)[1]
    b=rename_symbol(b,oldname,name)
    if name=='MCP251863T-E_SS':
        # KiCad's source symbol incorrectly calls TXD an output. Microchip
        # DS20006624B Table 1-1 defines transceiver TXD pin 23 as an input.
        for match in re.finditer(r'\(pin \w+ line',b):
            pin=block(b,match.start())
            if '(number "23"' in pin and '(name "TXD"' in pin:
                b=b.replace(pin,re.sub(r'^\(pin \w+', '(pin input',pin),1)
                break
        else:raise ValueError('MCP251863 TXD pin 23 not found')
    if name=='74AHC30PW,118':
        # The generic LS30 drawing omits physical NCs. Expose them on the power
        # unit so the MPN alias accounts for all fourteen package pads.
        child=block(b,b.index('(symbol "'+name+'_2_0"'))
        nc=''
        for number,y in [('9',-2.54),('10',-5.08),('13',-7.62)]:
            nc+=f'(pin no_connect line (at 10.16 {y} 180) (length 2.54) (name "NC" (effects (font (size 1 1)))) (number "{number}" (effects (font (size 1 1)))))'
        b=b.replace(child,child[:-1]+nc+')',1)
    b=re.sub(r'(\(property "Value" )"[^"]*"',lambda m:m[1]+json.dumps(name.replace('MCP251863T-E_SS','MCP251863T-E/SS').replace('TMR_6-0511','TMR 6-0511')),b,count=1)
    actual_footprints=selection[name]['footprints']
    assert len(actual_footprints)==1,(name,actual_footprints)
    actual_footprint=actual_footprints[0]
    b=re.sub(r'(\(property "Footprint" )"[^"]*"',lambda m:m[1]+json.dumps(actual_footprint),b,count=1)
    def prop(key,value):
        global b
        pattern=r'(\(property "'+re.escape(key)+r'" )"[^"]*"'
        if re.search(pattern,b):
            b=re.sub(pattern,lambda m:m[1]+json.dumps(value),b,count=1)
        else:
            b=b[:-1]+f'(property "{key}" {json.dumps(value)} (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes))))'
    prop('Description',desc)
    prop('MPN',name.replace('MCP251863T-E_SS','MCP251863T-E/SS'))
    prop('Manufacturer',selection[name]['manufacturer'])
    if name=='CC0603KRX7R9BB104':prop('Value','100n')
    datasheets={
      'MCP251863T-E_SS':'https://ww1.microchip.com/downloads/aemDocuments/documents/APID/ProductDocuments/DataSheets/MCP251863-Data-Sheet-DS20006624A.pdf',
      'ABM8G-40.000MHZ-18-D2Y-T':'https://abracon.com/Resonators/abm8g.pdf',
      'ESDONCAN1LT1G':'https://www.onsemi.com/pdf/datasheet/esdoncan1-d.pdf',
      'ISO7763DWR':'https://www.ti.com/lit/ds/symlink/iso7763.pdf',
      'TPS259530DSGR':'https://www.ti.com/lit/ds/symlink/tps2595.pdf',
      'TMR_6-0511':'https://www.tracopower.com/products/tmr6.pdf',
      'TLV75533PDBVR':'https://www.ti.com/lit/ds/symlink/tlv755p.pdf'}
    datasheets.update({
      '74LVC08APW,118':'https://assets.nexperia.com/documents/data-sheet/74LVC08A.pdf',
      '74LVC32APW,118':'https://assets.nexperia.com/documents/data-sheet/74LVC32A.pdf',
      '74AHC30PW,118':'https://assets.nexperia.com/documents/data-sheet/74AHC_AHCT30.pdf',
      '74LVC04AT14-13':'https://www.diodes.com/assets/Datasheets/74LVC04A.pdf'})
    datasheets.update({
      '0466001.NR':'https://www.littelfuse.com/assetdocs/fuse-466-datasheet?assetguid=dbe9bcd7-6072-4adf-bf5b-d33e52a6b90f',
      'AO3401A':'https://www.aosmd.com/sites/default/files/res/datasheets/AO3401A.pdf',
      'BZT52C6V8-13-F':'https://www.diodes.com/assets/Datasheets/ds18004.pdf',
      'CL10C270JB8NNNC':'https://www1.futureelectronics.com/doc/Samsung%20Electro-Mechanics/CL10C270JB8NNNC.pdf'})
    datasheets['RC0603FR-07100KL']='https://yageogroup.com/component-documentation/download/specsheet/RC0603FR-07100KL'
    prop('Datasheet',datasheets.get(name,url))
    if name in ('74LVC08APW,118','74LVC04AT14-13','74LVC32APW,118','74AHC30PW,118'):
        prop('ki_keywords',{'74LVC08APW,118':'LVC CMOS AND bank select','74LVC04AT14-13':'LVC CMOS inverter bank select','74LVC32APW,118':'LVC CMOS OR','74AHC30PW,118':'AHC CMOS NAND shared interrupt'}[name])
        prop('ki_fp_filters','TSSOP*14*4.4x5mm*P0.65mm*')
    symbols.append(b)
    manifest.append(dict(mpn=name.replace('MCP251863T-E_SS','MCP251863T-E/SS').replace('TMR_6-0511','TMR 6-0511'),quantity=qty,function=desc,symbol=LIB+':'+name,footprint=actual_footprint,step=';'.join(local_models),asset_origin=src or 'custom symbol from manufacturer pin table',supplier_url=url,observed_stock=stock,unit_usd=price,checked_date='2026-10-18' if name in ('0466001.NR','AO3401A','BZT52C6V8-13-F','RC0603FR-0710KL','CL10C270JB8NNNC') else '2026-10-17' if name in ('74LVC08APW,118','74LVC04AT14-13','74LVC32APW,118','74AHC30PW,118') else '2026-10-16'))
    manifest[-1].update(placed_references=';'.join(selection[name]['references']),
                        retention_reason=selection[name]['reason'])
    if name=='RC0603FR-07100KL':manifest[-1]['checked_date']='2026-10-18'

# Former selections and the unplaced termination jumper are intentionally
# omitted. The active schematic's generic C/R packages are retained above.
(ROOT/(LIB+'.kicad_sym')).write_text('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor")\n'+'\n'.join(symbols)+'\n)\n',encoding='utf-8')
with (ROOT/'asset_manifest.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=manifest[0].keys()); w.writeheader(); w.writerows(manifest)
(ROOT/'parts.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
for kind,uri in [('sym', '${KIPRJMOD}/../kicad_footprints/BreakoutBoard.kicad_sym'),('fp','${KIPRJMOD}/../kicad_footprints/BreakoutBoard.pretty')]:
    (ROOT/(kind+'-lib-table')).write_text(f'({kind}_lib_table\n (lib (name "BreakoutBoard")(type "KiCad")(uri "{uri}")(options "")(descr "BreakoutBoard selected parts"))\n)\n',encoding='utf-8')
hashes={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.rglob('*')) if p.suffix in ('.step','.kicad_sym','.kicad_mod') and 'SG-210' not in str(p)}
(ROOT/'sha256.json').write_text(json.dumps(hashes,indent=2),encoding='utf-8')
print(f'Bundled {len(manifest)} purchased part types, {len(symbols)} symbols, {len(list(FP.glob("*.kicad_mod")))} footprints, {len(list(MODELS.glob("*.step")))} STEP files.')
print('Run prune_library.py --apply to remove package files left by older builds.')
