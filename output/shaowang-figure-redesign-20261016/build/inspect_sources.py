from pathlib import Path
from pypdf import PdfReader
from docx import Document
import json, subprocess, zipfile, sys
sys.stdout.reconfigure(encoding='utf-8')
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
REF = Path('E:/wechatData/xwechat_files/wxid_c14weta2ez6m22_03f5/temp/RWTemp/2026-10/9e20f478899dc29eb19741386f9343c8')
inventory = []
for i, file in enumerate(REF.glob('*.pdf'), 1):
    reader = PdfReader(file)
    pages = []
    for n, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ''
        captions = [line for line in text.splitlines() if line.strip().startswith('图')]
        if captions:
            pages.append({'page': n, 'captions': captions})
    inventory.append({'id': i, 'file': str(file), 'count': len(reader.pages), 'figures': pages})
    (ROOT/'reference'/f'ref{i}.txt').write_text('\n\n'.join(p.extract_text() or '' for p in reader.pages),encoding='utf8')
    choices = [p['page'] for p in pages if p['page'] > 5][:16]
    for page in choices:
        if not (ROOT/'reference'/f'ref{i}-p{page}.png').exists():
            subprocess.run(['pdftoppm','-f',str(page),'-l',str(page),'-scale-to','1100','-singlefile','-png',str(file),str(ROOT/'reference'/f'ref{i}-p{page}')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    print(i, file.name, len(reader.pages), json.dumps(pages,ensure_ascii=False))
doc = Document('D:/dianzi/output/shaowang-report-20261016/deliverables/ShaoWang-技术报告.docx')
(ROOT/'report-text.txt').write_text('\n'.join(p.text for p in doc.paragraphs),encoding='utf8')
(ROOT/'source-inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding='utf8')
template=next(REF.glob('*.pptx'))
with zipfile.ZipFile(template) as z:
    ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
    slides=sorted([p for p in z.namelist() if p.startswith('ppt/slides/slide') and p.endswith('.xml')],key=lambda p:int(p.split('slide')[-1].split('.')[0]))
    print('TEMPLATE',len(slides))
    for p in slides:
        tree=ET.fromstring(z.read(p))
        print(p, ' '.join(n.text or '' for n in tree.findall('.//a:t',ns))[:300])
