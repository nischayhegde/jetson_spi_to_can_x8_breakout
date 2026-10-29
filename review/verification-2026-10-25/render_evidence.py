"""Read-only renders; the expanded schematic SVG is a review copy only."""
from pathlib import Path
import re
import pymupdf
OUT=Path(__file__).resolve().parent
path=OUT/'schematic/breakout.svg'
svg=path.read_text(encoding='utf-8')
svg=re.sub(r'viewBox="[^"]*"','viewBox="-100 -100 500 600"',svg,count=1)
svg=re.sub(r'width="[^"]*" height="[^"]*"','width="500mm" height="600mm"',svg,count=1)
(OUT/'schematic/full.svg').write_text(svg,encoding='utf-8')
doc=pymupdf.open(stream=svg.encode(),filetype='svg')
doc.get_page_pixmap(0,matrix=pymupdf.Matrix(1.0,1.0)).save(str(OUT/'schematic/full.png'))
for name in ('TXB0108',):
    doc=pymupdf.open(OUT/'sources'/f'{name}.pdf')
    for i,page in enumerate(doc):
        if '5.16 Switching' in page.get_text() and i>1:
            page.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5)).save(str(OUT/f'{name}-timing.png'))
