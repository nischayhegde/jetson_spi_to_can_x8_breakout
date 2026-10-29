"""Render the edited header and ground-plane connection for visual inspection."""
from pathlib import Path
import pymupdf
OUT=Path(__file__).resolve().parent
doc=pymupdf.open(OUT/'schematic/breakout.svg')
# SVG coordinates follow mm, rendered through MuPDF in points.
clip=pymupdf.Rect(27,68,104,132)*(72/25.4)
doc[0].get_pixmap(matrix=pymupdf.Matrix(4,4),clip=clip).save(str(OUT/'j1-schematic.png'))
doc=pymupdf.open(OUT/'ground-plane.svg')
doc[0].get_pixmap(matrix=pymupdf.Matrix(5,5)).save(str(OUT/'ground-plane.png'))
