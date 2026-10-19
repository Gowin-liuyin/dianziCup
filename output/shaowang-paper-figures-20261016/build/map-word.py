import json,hashlib
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
root=Path('D:/dianzi/output/shaowang-paper-figures-20261016')
source=Path('D:/dianzi/output/shaowang-report-20261016')
hashes={hashlib.sha256(p.read_bytes()).hexdigest():p.stem for p in (source/'fig').glob('*.png')}
ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships','wp':'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'}
with ZipFile(source/'deliverables/ShaoWang-技术报告.docx') as z:
 rels={r.get('Id'):r.get('Target') for r in E.fromstring(z.read('word/_rels/document.xml.rels'))}
 rootxml=E.fromstring(z.read('word/document.xml'));mapping=[]
 for i,shape in enumerate(rootxml.findall('.//wp:inline',ns),1):
  blip=shape.find('.//a:blip',ns);target=rels[blip.get('{'+ns['r']+'}embed')];digest=hashlib.sha256(z.read('word/'+target)).hexdigest()
  if digest in hashes:mapping.append({'inline_index':i,'id':hashes[digest]})
(root/'build/word-mapping.json').write_text(json.dumps(mapping),encoding='utf-8')
print('Original report inline figures matched:',len(mapping),'unique:',len(set(x['id'] for x in mapping)))
