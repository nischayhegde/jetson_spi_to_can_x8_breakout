"""Download datasheets for all selected BOM parts using normal system proxy settings.

Run from any directory: python C:/humanoids/breakoutboard/datasheets/download_datasheets.py
Never saves HTML/error responses with a .pdf extension. Preserves existing valid PDFs.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import csv
import hashlib
import json
import re
import urllib.request

ROOT = Path(__file__).resolve().parent
PARTS = json.loads((ROOT.parent/'kicad_footprints/parts.json').read_text(encoding='utf-8'))
SOURCES = {
 '74AHC30PW,118':('https://docs.ampnuts.ru/nexperia.com.datasheet/74AHC_AHCT30.pdf','Nexperia 74AHC/74AHCT30 older manufacturer datasheet from public mirror; current Rev. 8 reviewed online and linked in BOM/symbol'),
 '74LVC32APW,118':('https://www.farnell.com/datasheets/1645516.pdf','NXP 74LVC32A Rev. 5 (2011), distributor-hosted predecessor-brand datasheet; current Nexperia Rev. 11 linked in BOM/symbol'),
 '0466001.NR':('https://www.farnell.com/datasheets/3741073.pdf','Littelfuse 466 family datasheet, distributor-hosted copy including the selected 1 A row; current manufacturer link in BOM/symbol'),
 'AO3401A':('https://www.aosmd.com/sites/default/files/res/datasheets/AO3401A.pdf','Alpha & Omega Semiconductor AO3401A Rev. 3.1 (December 2023), original manufacturer datasheet'),
 'BZT52C6V8-13-F':('https://media.digikey.com/pdf/Data%20Sheets/Diodes%20PDFs/BZT52CV0%20-%20BZT52C39.pdf','Diodes Incorporated DS18004 Rev. 32-2 (June 2008), DigiKey-hosted original manufacturer family datasheet including 6.8 V and -13-F packaging; current manufacturer sheet linked in BOM/symbol'),
 'MCP251863T-E/SS':('https://ww1.microchip.com/downloads/aemDocuments/documents/APID/ProductDocuments/DataSheets/MCP251863-Data-Sheet-DS20006624A.pdf','Microchip device datasheet'),
 'ABM8G-40.000MHZ-18-D2Y-T':('https://abracon.com/Resonators/ABM8G.pdf','Abracon ABM8G family datasheet; selected options encoded in MPN'),
 'ESDONCAN1LT1G':('https://www.farnell.com/datasheets/2337848.pdf','onsemi ESDONCAN1 device datasheet, distributor-hosted older revision'),
 'ISO7763DWR':('https://www.ti.com/lit/ds/symlink/iso7763.pdf','TI ISO776x family datasheet'),
 'TMR 6-0511':('https://www.tracopower.com/products/tmr6.pdf','TRACO TMR 6 family datasheet'),
 'TPS259530DSGR':('https://www.ti.com/lit/ds/symlink/tps2595.pdf','TI TPS2595 family datasheet'),
 'TLV75533PDBVR':('https://www.ti.com/lit/ds/symlink/tlv755p.pdf','TI TLV755P family datasheet'),
 'CL10C270JB8NNNC':('https://www1.futureelectronics.com/doc/Samsung%20Electro-Mechanics/CL10C270JB8NNNC.pdf','Samsung exact-part specification sheet, distributor-hosted copy; 27 pF C0G 50 V +/-5%, 0603'),
 'CC0603KRX7R9BB104':('https://yageogroup.com/download/specsheet/CC0603KRX7R9BB104','YAGEO exact-part specification sheet'),
 'CGA3E1X7R1E105K080AC':('https://www.farnell.com/datasheets/1735392.pdf','TDK CGA series specification, distributor-hosted copy listing selected MPN'),
 'CL21B106KOQNNNE':('https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/926/CL_Series_MLCC_ds.pdf','Samsung CL series datasheet linked by DigiKey for selected MPN'),
 'CC0603KRX7R9BB103':('https://yageogroup.com/download/specsheet/CC0603KRX7R9BB103','YAGEO exact-part specification sheet'),
 'RC1206FR-07120RL':('https://yageogroup.com/content/datasheet/asset/file/PYU-RC_GROUP_51_ROHS_L','YAGEO RC_L family datasheet'),
 'RC0603FR-0710KL':('https://yageogroup.com/content/datasheet/asset/file/PYU-RC_GROUP_51_ROHS_L','YAGEO RC_L family datasheet'),
 'RC0603FR-0733RL':('https://yageogroup.com/content/datasheet/asset/file/PYU-RC_GROUP_51_ROHS_L','YAGEO RC_L family datasheet'),
 'CRCW06031K21FKEA':('https://www.vishay.com/doc?20035=','Vishay D/CRCW e3 family datasheet'),
 'B3B-XH-A':('https://www.jst-mfg.com/product/pdf/eng/eXH.pdf','JST XH series specification and dimensions'),
 'B2B-XH-A':('https://www.jst-mfg.com/product/pdf/eng/eXH.pdf','JST XH series specification and dimensions'),
 'M20-9982046':('https://content.harwin.com/m/7d31e750480889aa/original/C001-C001XX-Component-Specification-M20-Series-2-54mm-pitch-PCB-connectors.pdf','Harwin M20 component specification; also download M20-998 drawing'),
 '74LVC08APW,118':('https://store.comet.bg/download-file.php?id=14759','Nexperia quad AND gate datasheet Rev. 11, distributor-hosted copy; latest Rev. 12 linked in symbol/BOM'),
 '74LVC04AT14-13':('https://www.diodes.com/assets/Datasheets/74LVC04A.pdf','Diodes Incorporated hex inverter datasheet'),
}
SUPPLEMENTS = [
 ('M20-998_Drawing.pdf','https://content.harwin.com/asset/1590d228-db5c-4836-ab0c-0f146730b624/DRG-00478-Technical-Drawing-Datasheet-M20-998-pdf.pdf','Harwin M20-998 family dimensional drawing'),
 ('MCP251863_Board_Design_Hints.pdf','https://ww1.microchip.com/downloads/aemDocuments/documents/APID/ApplicationNotes/ApplicationNotes/MCP251863-Application-Note-00004560A.pdf','Microchip board design application note'),
 ('MOSFET_Reverse_Protection_TI.pdf','https://www.ti.com/lit/an/slvae57/slvae57.pdf','TI Basics of Ideal Diodes, P-channel reverse-hookup topology and reverse-current limitations'),
]

def valid_pdf(data):
    return data[:1024].lstrip().startswith(b'%PDF-') and b'%%EOF' in data[-4096:]

def download(job):
    name, filename, url, kind = job
    dest=ROOT/filename
    row=dict(mpn=name,filename=filename,document=kind,source_url=url,status='missing',bytes=0,sha256='',checked_utc=datetime.now(timezone.utc).isoformat(),error='')
    try:
        if dest.exists() and valid_pdf(dest.read_bytes()):
            data=dest.read_bytes(); row['status']='present'
        else:
            req=urllib.request.Request(url,headers={'User-Agent':'BreakoutBoard-Datasheet-Archive/1.0'})
            with urllib.request.urlopen(req,timeout=25) as response:
                data=response.read(30_000_001)
                row['resolved_url']=response.url
            if len(data)>30_000_000: raise ValueError('File exceeds 30 MB limit')
            if not valid_pdf(data): raise ValueError('Response is not a PDF with a header and EOF marker; not saved')
            tmp=dest.with_suffix('.pdf.part');tmp.write_bytes(data);tmp.replace(dest)
            row['status']='downloaded'
        row['bytes']=len(data);row['sha256']=hashlib.sha256(data).hexdigest()
    except Exception as e:
        row['error']=str(e)
    return row

def main():
    assert set(SOURCES)=={p['mpn'] for p in PARTS},'Datasheet map does not match BOM'
    jobs=[(p['mpn'],re.sub(r'[^A-Za-z0-9_.-]','_',p['mpn'])+'.pdf',*SOURCES[p['mpn']]) for p in PARTS]
    jobs += [('Supplement',filename,url,kind) for filename,url,kind in SUPPLEMENTS]
    with ThreadPoolExecutor(max_workers=6) as pool: rows=list(pool.map(download,jobs))
    (ROOT/'download_manifest.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    with (ROOT/'download_manifest.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['mpn','filename','document','source_url','status','bytes','sha256','checked_utc','error','resolved_url']);w.writeheader();w.writerows(rows)
    n=sum(r['status']!='missing' for r in rows)
    md=['# Datasheet archive', '',f'Local PDFs: **{n}/{len(rows)} documents**, covering {len(PARTS)} component-library inventory part numbers plus {len(SUPPLEMENTS)} supplements.', '',
        'A link is not a downloaded PDF. The status column records the actual local result. Documents may cover a family, and some are part-specific specification or characterization sheets as identified below.','',
        '| Part | Intended local filename | Document / source | Local status |','|---|---|---|---|']
    for r in rows:
        md.append(f"| {r['mpn']} | {r['filename']} | [{r['document']}]({r['source_url']}) | {r['status']} |")
    md += ['', '## Download / retry','', 'Run from the repository root:', '', '```powershell','python .\\datasheets\\download_datasheets.py','```','',
           'The downloader uses ordinary system proxy settings; it does not bypass the environment network restrictions. It validates PDF header/trailer markers, preserves valid existing files, and records source URLs, timestamps, file sizes, hashes and errors. Full PDF rendering and electrical applicability still need review.', '',
           '## Latest attempt','']
    errors=sorted({r['error'] for r in rows if r['error']})
    if errors: md += [f'- {e}' for e in errors]
    else: md += ['All listed PDFs are present.']
    (ROOT/'README.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
    print(f'{n}/{len(rows)} PDFs present; {len(rows)-n} missing. See datasheets/README.md and download_manifest.csv.')
    return 0 if n==len(rows) else 1

if __name__=='__main__': raise SystemExit(main())
