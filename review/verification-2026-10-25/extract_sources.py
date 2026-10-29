"""Extract locally archived datasheets and explicitly named primary sources."""
from pathlib import Path
import json, urllib.request, hashlib
import pymupdf
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
sources={
 'RobStride04_Manual.pdf':'https://www.robstride.com/assets/product_manual_robStride04-37549d59.pdf',
 'MCP251863_RevB.pdf':'https://ww1.microchip.com/downloads/aemDocuments/documents/APID/ProductDocuments/DataSheets/MCP251863-External-CAN-FD-Controller-with-Integrated-Transceiver-DS20006624.pdf',
 'MCP251863_ErrataB.pdf':'https://ww1.microchip.com/downloads/aemDocuments/documents/APID/ProductDocuments/Errata/MCP251863-Silicon-Errata-and-Data-Sheet-Clarification-DS80000984.pdf',
 'Jetson_carrier_v1_3.pdf':'https://developer.nvidia.com/downloads/assets/embedded/secure/jetson/orin_nano/docs/jetson_orin_nano_devkit_carrier_board_specification_sp.pdf',
 'TXB0108.pdf':'https://www.ti.com/lit/ds/symlink/txb0108.pdf',
 '74LVC32A_Rev11.pdf':'https://assets.nexperia.com/documents/data-sheet/74LVC32A.pdf',
 '74AHC30_Rev8.pdf':'https://assets.nexperia.com/documents/data-sheet/74AHC_AHCT30.pdf',
 'mcp251xfd-core.c':'https://raw.githubusercontent.com/torvalds/linux/master/drivers/net/can/spi/mcp251xfd/mcp251xfd-core.c',
 'mcp251xfd-rx.c':'https://raw.githubusercontent.com/torvalds/linux/master/drivers/net/can/spi/mcp251xfd/mcp251xfd-rx.c',
 'mcp251xfd-tx.c':'https://raw.githubusercontent.com/torvalds/linux/master/drivers/net/can/spi/mcp251xfd/mcp251xfd-tx.c',
 'mcp251xfd-regmap.c':'https://raw.githubusercontent.com/torvalds/linux/master/drivers/net/can/spi/mcp251xfd/mcp251xfd-regmap.c',
 'spi-mux.c':'https://raw.githubusercontent.com/torvalds/linux/master/drivers/spi/spi-mux.c',
 'spi-tegra114.c':'https://raw.githubusercontent.com/torvalds/linux/master/drivers/spi/spi-tegra114.c',
}
folder=OUT/'sources'; folder.mkdir(exist_ok=True)
manifest=[]
for name,url in sources.items():
    dest=folder/name
    try:
        if not dest.exists():
            request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
            dest.write_bytes(urllib.request.urlopen(request,timeout=40).read())
        if name.endswith('.pdf') and not dest.read_bytes().startswith(b'%PDF'): raise ValueError('not PDF')
        manifest.append({'file':name,'url':url,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
        print(name, dest.stat().st_size, flush=True)
    except Exception as e:
        manifest.append({'file':name,'url':url,'error':str(e)}); print(name,str(e),flush=True)
(OUT/'source_manifest.json').write_text(json.dumps(manifest,indent=2))
for src in list((ROOT/'datasheets').glob('*.pdf'))+list(folder.glob('*.pdf')):
    try:
        doc=pymupdf.open(src)
        text='\n'.join(f'\n=== PDF PAGE {i+1} ===\n'+p.get_text() for i,p in enumerate(doc))
        (folder/(src.stem+'.txt')).write_text(text,encoding='utf-8')
    except Exception as e: print(src.name,str(e))
