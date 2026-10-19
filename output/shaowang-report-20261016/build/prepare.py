from pathlib import Path
import json
import re
from docx import Document

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'source' / 'astra-pack'
dossier = (SOURCE / 'design-dossier.md').read_text(encoding='utf-8')
parts = re.split(r'(?=^## D\d+ )', dossier, flags=re.M)
sections = {re.search(r'^## (D\d+)', p).group(1): p for p in parts if p.startswith('## D')}
(ROOT/'build/dossier-sections.json').write_text(json.dumps(sections, ensure_ascii=False, indent=2), encoding='utf-8')
(ROOT/'build/口径核对表.md').write_text('# 写作口径核对表\n\n'+sections['D2']+'\n'+sections['D20'], encoding='utf-8')
doc = Document(SOURCE/'technical-report.docx')
blocks=[]
for item in doc.element.body:
    if item.tag.endswith('}p'):
        from docx.text.paragraph import Paragraph
        p=Paragraph(item,doc)
        blocks.append({'type':'paragraph','text':p.text,'style':p.style.name})
    elif item.tag.endswith('}tbl'):
        from docx.table import Table
        t=Table(item,doc)
        blocks.append({'type':'table','rows':[[c.text for c in r.cells] for r in t.rows]})
(ROOT/'build/old-blocks.json').write_text(json.dumps(blocks,ensure_ascii=False,indent=2),encoding='utf-8')
figs=[]
for row in sections['D22'].splitlines():
    if row.startswith('| F-'):
        cols=[c.strip() for c in row.strip('|').split('|')]
        figs.append(dict(zip(['id','location','title','purpose','elements','layout','old','source'],cols)))
(ROOT/'build/figures.json').write_text(json.dumps(figs,ensure_ascii=False,indent=2),encoding='utf-8')
tables=[]
for row in sections['D22'].splitlines():
    if row.startswith('| T-'):
        cols=[c.strip() for c in row.strip('|').split('|')]
        tables.append(dict(zip(['id','location','title','source'],cols)))
(ROOT/'build/tables.json').write_text(json.dumps(tables,ensure_ascii=False,indent=2),encoding='utf-8')
print('prepared',len(blocks),'blocks',len(figs),'figures',len(tables),'tables')
