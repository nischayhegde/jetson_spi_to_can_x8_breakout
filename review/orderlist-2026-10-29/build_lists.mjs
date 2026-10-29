import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {Workbook, SpreadsheetFile} from '@oai/artifact-tool';

const out=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(out,'../..');
const data=JSON.parse(await fs.readFile(path.join(out,'order_data.json'),'utf8'));
const rows=data.rows;
const firstRow=7,lastRow=firstRow+rows.length-1,totalRow=lastRow+2,endRow=totalRow+4;
if(process.argv.includes('--help-links')){
  const probe=Workbook.create();
  console.log(probe.help('range hyperlinks',{search:'hyperlink',include:'index,examples,notes',maxChars:5000}).ndjson);
  process.exit(0);
}
for(const [relative,expected] of Object.entries(data.cad_sha256)){
  const current=createHash('sha256').update(await fs.readFile(path.join(root,relative))).digest('hex');
  if(current!==expected) throw new Error(`CAD changed since inventory extraction: ${relative}`);
}

const money=n=>n==null?'n.a.':`$${Number(n).toFixed(2)}`;
const unit=n=>n==null?'n.a.':`$${Number(n).toFixed(4).replace(/0+$/,'').replace(/\.$/,'')}`;
const count=n=>n==null?'Unverified':Number(n).toLocaleString('en-US');
const esc=s=>String(s??'').replaceAll('|','\\|').replaceAll('\n',' ');
const link=(label,url)=>`[${label}](${url})`;
const formulaLink=(label,url)=>`=HYPERLINK("${url.replaceAll('"','""')}","${label}")`;
function csvCell(v){const s=v==null?'':String(v);return /[",\r\n]/.test(s)?'"'+s.replaceAll('"','""')+'"':s;}
async function csvFromArtifact(filename,headers,records){
  const wb=Workbook.create();
  const sh=wb.worksheets.add('Data');
  const matrix=[headers,...records.map(r=>headers.map(h=>r[h]??null))];
  const range=sh.getRangeByIndexes(0,0,matrix.length,headers.length);
  range.values=matrix;
  wb.recalculate();
  const actual=range.values;
  if(actual.length!==records.length+1) throw new Error('Unexpected CSV row count');
  await fs.writeFile(path.join(root,filename),'\uFEFF'+actual.map(r=>r.map(csvCell).join(',')).join('\r\n')+'\r\n');
}

const componentHeaders=['mpn','manufacturer','quantity','schematic_quantity','board_quantity',
  'placed_references','design_value','footprint','function','specifications','status',
  'mouser_url','digikey_url','notes'];
await csvFromArtifact('componentlist.csv',componentHeaders,rows);
const orderHeaders=['mpn','manufacturer','quantity','order_quantity','spares','placed_references',
  'design_value','footprint','specifications','digikey_sku','digikey_stock','digikey_status',
  'digikey_unit_usd','line_usd','digikey_url','mouser_stock','mouser_status',
  'mouser_unit_usd','mouser_line_usd','mouser_url','mouser_evidence_url',
  'checked_date','unit_price_basis','notes','sourcing_note'];
await csvFromArtifact('orderlist.csv',orderHeaders,rows);

const componentText=[
  '# SPI to eight-channel CAN PCB component list',
  '',
  'Updated 2026-10-29 from the saved schematic and PCB. Quantities are for one board and count physical packages, including multi-unit logic ICs only once.',
  '',
  `**${data.purchase_lines} purchase lines, ${data.fitted_packages} fitted components.** The PCB also contains 21 bare test pads and four mounting holes. These features require no purchased component. Package identities, references and purchasing fields are synchronized across the schematic and PCB. Circuit connectivity is unchanged.`,
  '',
  '**Standardized parts:** all eight 120-ohm CAN terminations use **RC1206FR-07120RL**, 1%, 0.25 W, 1206. J1 uses **M20-7832046** and the matching female socket footprint in the schematic, PCB and order list. '+link('YAGEO resistor specification','https://yageogroup.com/component-documentation/download/specsheet/RC1206FR-07120RL')+'; '+link('Harwin socket specification','https://www.harwin.com/products/M20-7832046')+'.',
  '',
  '| Function | Manufacturer part to purchase | Qty | References | Existing PCB footprint | Mouser | DigiKey |',
  '|---|---|---:|---|---|---|---|',
  ...rows.map(r=>`| ${esc(r.function)} | ${esc(r.mpn)} | ${r.quantity} | ${esc(r.placed_references.replaceAll(';',', '))} | ${esc(r.footprint)} | ${link(r.mpn==='AO3401A'?'Search only':'Listing',r.mouser_url)} | ${link('Listing',r.digikey_url)} |`),
  '',
  'TP13 and TP14 use M20-9990246 two-pin 2.54 mm headers. F1 is present in the design. The 28 x 100 nF bypass capacitors use standard references C1 and C21-C47, with their exact MPN stored separately from the displayed value.',
  '',
  'Bare test pads: TP1-TP12 and TP15-TP23, 21 total. Mounting holes: H1-H4. Neither group belongs in a purchase cart. Mating cable housings, contacts, cables, screws and standoffs are outside this fitted-PCB list.',
  '',
  'The separate '+link('order list','orderlist.md.txt')+' records order quantities, supplier stock, applicable USD prices and the dated sourcing limitations. No obsolete or unplaced design options are included.',
  ''
].join('\n');
await fs.writeFile(path.join(root,'componentlist.md.txt'),componentText);

const orderText=[
  '# PCB parts order list',
  '',
  `**One board: ${data.fitted_packages} fitted components, ${data.purchase_lines} purchase lines. Order ${data.order_quantity} pieces from DigiKey for a quoted parts subtotal of ${money(data.digikey_subtotal_usd)}.** The ${data.spares} extra resistors reduce the order cost at the published quantity breaks. Every DigiKey line below showed stock sufficient for its order quantity in the retrieved listing.`,
  '',
  'Supplier snapshots retrieved **2026-10-29**. Web pages may be cached, so these are listing snapshots rather than a live reserved cart. USD prices exclude shipping, tax, tariffs and assembly. Use cut tape for SMD parts and bulk/tube for connectors. Do not select paid reeling. Mouser unit and line prices use the same order quantity for comparison; unverified stock is not treated as available.',
  '',
  '| Manufacturer part | Needed | Order | DigiKey USD each | DigiKey USD line | DigiKey stock | DigiKey | Mouser USD each | Mouser stock | Mouser |',
  '|---|---:|---:|---:|---:|---:|---|---:|---:|---|',
  ...rows.map(r=>`| ${esc(r.mpn)} | ${r.quantity} | ${r.order_quantity} | ${unit(r.digikey_unit_usd)} | ${money(r.line_usd)} | ${count(r.digikey_stock)} | ${link('Listing',r.digikey_url)} | ${unit(r.mouser_unit_usd)} | ${count(r.mouser_stock)} | ${link(r.mpn==='AO3401A'?'Search only':'Listing',r.mouser_url)} |`),
  `| **Total** | **${data.fitted_packages}** | **${data.order_quantity}** | | **${money(data.digikey_subtotal_usd)}** | | | | | |`,
  '',
  'Order ten RC1206FR-07120RL for eight fitted positions, ten RC0603FR-0710KL for nine fitted positions, and ten RC0603FR-07100KL for four fitted positions. All other order quantities equal the fitted quantity. No discretionary spare ICs or connectors are added.',
  '',
  '**Footprint matching:** R6/R10/R13/R16/R23/R26/R29/R32 all use the same 1206 termination footprint and MPN. J1 consistently specifies the female M20-7832046 socket. TP13/TP14 specify M20-9990246 two-pin headers. MPN and Manufacturer fields in the schematic and PCB drive this list. The standardization changed R26\'s package and local bottom routing, corrected metadata and capacitor references, and retained every circuit connection.',
  '',
  '**Mouser exceptions:** AO3401A has a clearly labeled search link because an exact Alpha & Omega product listing was not verified. The Samsung 27 pF capacitor has an exact regional listing, but its stock and USD price were not verified. C20 and the white three-pin JST connector also lack verified current Mouser stock. The DigiKey entries retain the standardized CAD\'s specified MPNs.',
  '',
  '| Supplier observation | Source and detail |',
  '|---|---|',
  ...rows.filter(r=>r.sourcing_note).map(r=>`| ${r.mpn} | ${link('Source',r.mouser_evidence_url)}. ${r.sourcing_note} |`),
  '',
  'Exact references, complete footprint names and supplier SKUs are in '+link('the CSV','orderlist.csv')+' and '+link('the workbook','orderlist.xlsx')+'. The fitted-only BOM is in '+link('componentlist','componentlist.md.txt')+'.',
  ''
].join('\n');
await fs.writeFile(path.join(root,'orderlist.md.txt'),orderText);

const wb=Workbook.create();
const sheet=wb.worksheets.add('Order list');
sheet.showGridLines=false;
sheet.tabColor='#243B53';
const headers=['Manufacturer part','Needed','Order','DigiKey USD each','DigiKey USD line','DigiKey stock',
  'Mouser USD each','Mouser USD line','Mouser stock','DigiKey','Mouser','',
  'References','Existing PCB footprint','Notes'];
sheet.getRange('A2').values=[['PCB parts for one board']];
sheet.getRange('A3').values=[[`${data.fitted_packages} fitted components. Order ${data.order_quantity} pieces across ${data.purchase_lines} purchase lines.`]];
sheet.getRange('A4').values=[['2026-10-29 listing snapshots. USD excludes shipping, tax and tariffs. Standardized CAD; circuit connectivity unchanged.']];
sheet.getRange('A6:O6').values=[headers];
const shortRefs=r=>r.mpn==='CC0603KRX7R9BB104'?'C1, C21-C47':r.placed_references.replaceAll(';',', ');
const body=rows.map(r=>[r.mpn,r.quantity,r.order_quantity,r.digikey_unit_usd,r.line_usd,r.digikey_stock,
  r.mouser_unit_usd??'n.a.',r.mouser_line_usd??'n.a.',r.mouser_stock??'Unverified',null,null,null,
  shortRefs(r),r.footprint,r.notes||r.sourcing_note]);
sheet.getRange(`A7:O${lastRow}`).values=body;
sheet.getRange(`E7:E${lastRow}`).formulas=rows.map((r,i)=>[`=ROUND(C${i+7}*D${i+7},2)`]);
sheet.getRange(`H7:H${lastRow}`).formulas=rows.map((r,i)=>r.mouser_unit_usd===null?['="n.a."']:[`=ROUND(C${i+7}*G${i+7},2)`]);
// This runtime cannot evaluate HYPERLINK. Native hyperlink relationships are
// added after export by add_native_hyperlinks.py; cell labels render normally.
sheet.getRange(`J7:K${lastRow}`).values=rows.map(r=>['DigiKey',r.mpn==='AO3401A'?'Search only':'Mouser']);
sheet.getRange(`A${totalRow}`).values=[['DigiKey order total']];
sheet.getRange(`B${totalRow}:C${totalRow}`).formulas=[[`=SUM(B7:B${lastRow})`,`=SUM(C7:C${lastRow})`]];
sheet.getRange(`E${totalRow}`).formulas=[[`=SUM(E7:E${lastRow})`]];
sheet.getRange(`G${totalRow}`).values=[['Mouser total']];
sheet.getRange(`H${totalRow}`).values=[['Incomplete']];
sheet.getRange(`A${totalRow+2}`).values=[['Extras: 2 x 1206 120-ohm, 1 x 10-kohm, 6 x 100-kohm resistors. Published quantity breaks lower the line totals.']];
sheet.getRange(`A${totalRow+3}`).values=[['All eight terminations: RC1206FR-07120RL, 1206, 0.25 W. J1: M20-7832046 female socket. MPN fields match CAD.']];
sheet.getRange(`A${endRow}`).values=[['Mouser AO3401A is search only. Unverified stock and missing USD prices are shown explicitly.']];
sheet.getRange(`A2:O${endRow}`).format.font={name:'Arial',size:10,color:'#172B4D'};
sheet.getRange('A2').format.font={name:'Arial',size:15,bold:true};
sheet.getRange('A3:A4').format.font={name:'Arial',size:10,color:'#5C6774'};
sheet.getRange('A6:K6').format={fill:'#243B53',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},
  wrapText:true,horizontalAlignment:'center',verticalAlignment:'center',rowHeight:34};
sheet.getRange('M6:O6').format={fill:'#52677E',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},
  wrapText:true,horizontalAlignment:'center',verticalAlignment:'center',rowHeight:34};
sheet.getRange(`A7:O${lastRow}`).format.rowHeight=25;
sheet.getRange(`A7:O${lastRow}`).format.verticalAlignment='center';
sheet.getRange(`B7:I${totalRow}`).format.horizontalAlignment='right';
sheet.getRange(`B7:C${totalRow}`).setNumberFormat('0');
sheet.getRange(`D7:D${lastRow}`).setNumberFormat('$0.0000');
sheet.getRange(`G7:G${lastRow}`).setNumberFormat('$0.0000');
sheet.getRange(`E7:E${totalRow}`).setNumberFormat('$0.00');
sheet.getRange(`H7:H${lastRow}`).setNumberFormat('$0.00');
sheet.getRange(`F7:F${lastRow}`).setNumberFormat('#,##0');
sheet.getRange(`I7:I${lastRow}`).setNumberFormat('#,##0');
sheet.getRange(`J7:K${lastRow}`).format.font={name:'Arial',size:10,color:'#1557A5'};
sheet.getRange(`J7:K${lastRow}`).format.horizontalAlignment='center';
for(let i=0;i<rows.length;i++) if(i%2===1){
  sheet.getRange(`A${i+7}:K${i+7}`).format.fill='#F2F5F8';
}
sheet.getRange(`A${totalRow}:K${totalRow}`).format.fill='#DFE7EF';
sheet.getRange(`A${totalRow}:K${totalRow}`).format.font={name:'Arial',size:10,bold:true,color:'#172B4D'};
sheet.getRange(`A${totalRow}:K${totalRow}`).format.rowHeight=28;
const widths={A:34,B:8,C:8,D:14,E:14,F:15,G:14,H:14,I:15,J:13,K:13,L:3,M:65,N:94,O:160};
for(const [col,width] of Object.entries(widths))sheet.getRange(`${col}1:${col}${endRow}`).format.columnWidth=width;
sheet.freezePanes.freezeRows(6);
sheet.freezePanes.freezeColumns(1);
wb.recalculate();
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#N/A|not implemented',
  options:{useRegex:true,maxResults:20},maxChars:2000});
await fs.writeFile(path.join(out,'workbook-inspection.json'),JSON.stringify(errors,null,2));
const total=sheet.getRange(`E${totalRow}`).values[0][0];
if(typeof total!=='number'||Math.abs(total-data.digikey_subtotal_usd)>.0001)
  throw new Error(`Subtotal mismatch: ${total}`);
const xlsx=await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(path.join(root,'orderlist.xlsx'));
const preview=await wb.render({sheetName:'Order list',range:`A1:K${endRow}`,scale:1.4,format:'png'});
await fs.writeFile(path.join(out,'orderlist-preview.png'),new Uint8Array(await preview.arrayBuffer()));
for(const [relative,expected] of Object.entries(data.cad_sha256)){
  if(createHash('sha256').update(await fs.readFile(path.join(root,relative))).digest('hex')!==expected)
    throw new Error(`Unexpected CAD mutation: ${relative}`);
}
console.log(JSON.stringify({lines:rows.length,fitted:data.fitted_packages,ordered:data.order_quantity,subtotal:total,
  outputs:['componentlist.md.txt','componentlist.csv','orderlist.md.txt','orderlist.csv','orderlist.xlsx'],
  cadUnchangedDuringListGeneration:true}));
