import json,hashlib,struct
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from lxml import etree as E
from pypdf import PdfReader
from PIL import Image
root=Path('D:/dianzi/output/shaowang-paper-figures-20261016');out=root/'deliverables'
meta=json.loads((root/'build/figure-metadata.json').read_text());ids=[r['id'] for r in meta]
ns={'p':'http://schemas.openxmlformats.org/presentationml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
checks=[]
def check(name,condition,detail):
 checks.append({'name':name,'passed':bool(condition),'detail':detail})
ppt=out/'ShaoWang-论文整图可编辑.pptx'
with ZipFile(ppt) as z:
 slides=[n for n in z.namelist() if __import__('re').fullmatch(r'ppt/slides/slide\d+\.xml',n)]
 check('slide_count',len(slides)==29,len(slides))
 counts={'groups':0,'tables':0,'pictures':0,'shapes':0,'connectors':0};minimum=[]
 for i,row in enumerate(meta,1):
  r=E.fromstring(z.read(f'ppt/slides/slide{i}.xml'))
  for k,t in [('groups','p:grpSp'),('tables','a:tbl'),('pictures','p:pic'),('shapes','p:sp'),('connectors','p:cxnSp')]:counts[k]+=len(r.findall('.//'+t,ns))
  fonts=[float(x.get('sz'))/100 for x in r.findall('.//a:rPr',ns) if x.get('sz')]
  physical=min(fonts)*(15.5/2.54*72)/((row['crop_pixels'][2]-row['crop_pixels'][0])*900/2400)
  minimum.append(physical)
  check(f"{row['id']}_font_at_15_5cm",physical>=8.4,round(physical,2))
  txt=''.join(r.itertext())
  if row['id'] in ['F-03','F-10','F-27','F-30']:check(row['id']+'_pending_marker','待测' in txt,'Retained target/pending distinction')
 check('editable_shapes',counts['shapes']>500,counts['shapes'])
 check('native_tables',counts['tables']==2,counts['tables'])
 check('whole_diagram_groups',counts['groups']==27,counts['groups'])
 check('no_raster_diagrams',counts['pictures']==0,counts['pictures'])
for fid in ids:
 emf=(out/f'emf/{fid}.emf').read_bytes()
 check(fid+'_EMF',emf[40:44]==b' EMF',len(emf))
 p=PdfReader(out/f'pdf/{fid}.pdf').pages[0]
 check(fid+'_PDF_width',abs(float(p.mediabox.width)-15.5/2.54*72)<.01,round(float(p.mediabox.width),3))
 im=Image.open(out/f'png/{fid}.png');check(fid+'_PNG_resolution',im.width>=2100,list(im.size))
check('preview_pages',len(PdfReader(out/'ShaoWang-论文配图预览.pdf').pages)==29,29)
check('proof_pages',len(PdfReader(out/'ShaoWang-论文版心插图样张.pdf').pages)==6,6)
audit={'checks':checks,'passed':sum(c['passed'] for c in checks),'total':len(checks),'native_objects':counts,'minimum_paper_font_pt':round(min(minimum),2),'pptx_sha256':hashlib.sha256(ppt.read_bytes()).hexdigest(),'visual_review':'All 29 PowerPoint renderings and 6 actual Word insertion pages inspected; revisions F04/F07/F24 rerendered and reinspected.'}
(root/'build/artifact-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in audit.items() if k not in ['checks','visual_review']},ensure_ascii=False))
assert audit['passed']==audit['total']
