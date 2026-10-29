"""Add Excel-native links missing from the authoring runtime's public API."""
from pathlib import Path
import json
import zipfile
import xml.etree.ElementTree as ET

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
workbook=ROOT/'orderlist.xlsx'
data=json.loads((OUT/'order_data.json').read_text())
S='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
P='http://schemas.openxmlformats.org/package/2006/relationships'
ET.register_namespace('',S)
ET.register_namespace('r',R)
with zipfile.ZipFile(workbook) as source:
    parts={n:source.read(n) for n in source.namelist()}
sheet_name='xl/worksheets/sheet1.xml'
rels_name='xl/worksheets/_rels/sheet1.xml.rels'
sheet=ET.fromstring(parts[sheet_name])
old=sheet.find(f'{{{S}}}hyperlinks')
if old is not None:
    sheet.remove(old)
rels=ET.fromstring(parts[rels_name]) if rels_name in parts else ET.Element(f'{{{P}}}Relationships')
for rel in list(rels):
    if rel.attrib.get('Id','').startswith('supplierLink'):
        rels.remove(rel)
links=ET.Element(f'{{{S}}}hyperlinks')
for i,row in enumerate(data['rows'],7):
    for col,supplier in [('J','digikey'),('K','mouser')]:
        identity=f'supplierLink{col}{i}'
        ET.SubElement(links,f'{{{S}}}hyperlink',{'ref':f'{col}{i}',f'{{{R}}}id':identity})
        ET.SubElement(rels,f'{{{P}}}Relationship',{'Id':identity,
            'Type':R+'/hyperlink','Target':row[supplier+'_url'],'TargetMode':'External'})
after_hyperlinks={'printOptions','pageMargins','pageSetup','headerFooter','rowBreaks','colBreaks',
 'customProperties','cellWatches','ignoredErrors','smartTags','drawing','legacyDrawing',
 'legacyDrawingHF','picture','oleObjects','controls','webPublishItems','tableParts','extLst'}
index=next((i for i,c in enumerate(sheet) if c.tag.split('}')[-1] in after_hyperlinks),len(sheet))
sheet.insert(index,links)
parts[sheet_name]=ET.tostring(sheet,encoding='utf-8',xml_declaration=True)
parts[rels_name]=ET.tostring(rels,encoding='utf-8',xml_declaration=True)
temporary=OUT/'orderlist-native-links.xlsx'
with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as target:
    for name,content in parts.items():
        target.writestr(name,content)
temporary.replace(workbook)
print(f'Added {len(data["rows"])*2} native Excel hyperlinks; numeric data and formulas preserved.')
