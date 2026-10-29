"""Render KiCad's final layout exports and a dimensioned review preview."""
from pathlib import Path
import re
import pymupdf

OUT = Path(__file__).resolve().parent
for side in ('front','back','ground'):
    path = OUT/f'after-{side}.svg'
    doc = pymupdf.open(path)
    doc[0].get_pixmap(matrix=pymupdf.Matrix(4,4)).save(str(path.with_suffix('.png')))

# This SVG is a review drawing; fabrication geometry remains in the KiCad board.
source = (OUT/'after-front.svg').read_text()
source = source[source.index('<svg'):]
source = source[:source.rindex('</svg>')+6]
width, height = map(float, re.search(r'viewBox="0\.0000 0\.0000 ([\d.]+) ([\d.]+)"',source).groups())
source = re.sub(r'<svg\b[^>]*>',
                f'<g transform="translate(8 18) scale({81/width} {80/height})">',source,count=1)
source = source.replace('</svg>','</g>')
source = source.replace('#F2EDA1','#5F6570').replace('#D0D2CD','#26364B')
preview = '''<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="115mm" viewBox="0 0 100 115">
<rect width="100" height="115" fill="white"/>
<g font-family="Arial,sans-serif" fill="#1B2E43">
<text x="8" y="6" font-size="3.1" font-weight="bold">Four corner mounting holes</text>
<text x="8" y="11" font-size="2.25">3.2 mm NPTH for M3 screws / standoffs</text>
</g>
'''+source+'''
<rect x="8" y="18" width="81" height="80" fill="none" stroke="#26364B" stroke-width="0.2"/>
<g stroke="#55758D" stroke-width="0.18" fill="none">
<path d="M8 100 V104 M89 100 V104 M8 102 H89 M7.3 102.7 L8.7 101.3 M88.3 102.7 L89.7 101.3"/>
<path d="M91 18 H95 M91 98 H95 M93 18 V98 M92.3 18.7 L93.7 17.3 M92.3 98.7 L93.7 97.3"/>
</g>
<g font-family="Arial,sans-serif" fill="#1B2E43" text-anchor="middle" font-size="2.4">
<text x="48.5" y="106.4">81 mm (previously 77 mm)</text>
<text x="97" y="58" transform="rotate(-90 97 58)">80 mm</text>
<text x="48.5" y="111.5" font-size="2.15">Hole spacing: 73 x 72 mm. Centers: 4 mm from edges.</text>
</g></svg>'''
(OUT/'layout-preview.svg').write_text(preview)
doc = pymupdf.open(stream=preview.encode(),filetype='svg')
doc[0].get_pixmap(matrix=pymupdf.Matrix(4,4)).save(str(OUT/'layout-preview.png'))
print(OUT/'layout-preview.png')
