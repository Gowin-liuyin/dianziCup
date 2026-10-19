from pathlib import Path
from zipfile import ZipFile
from lxml import etree
from PIL import Image, ImageOps, ImageDraw
from pypdf import PdfReader
import json

B = Path(__file__).resolve().parent
R = B.parent
pdf = PdfReader(B/'report.pdf')
pages = len(pdf.pages)
ns = {'p':'http://schemas.openxmlformats.org/presentationml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
with ZipFile(R/'deliverables/ShaoWang-图源.pptx') as z:
    slides = [etree.fromstring(z.read(n)) for n in z.namelist() if n.startswith('ppt/slides/slide') and n.endswith('.xml')]
    counts = {k:sum(len(s.findall('.//'+v,ns)) for s in slides) for k,v in [('shapes','p:sp'),('pictures','p:pic'),('connectors','p:cxnSp'),('start_connections','a:stCxn'),('end_connections','a:endCxn')]}
    notes = len([n for n in z.namelist() if n.startswith('ppt/notesSlides/notesSlide') and n.endswith('.xml')])
assets=[]
for p in sorted((R/'deliverables/fig').glob('*.png')):
    with Image.open(p) as im:
        assets.append({'name':p.stem,'size':im.size,'dpi':im.info.get('dpi'),'vector_pages':len(PdfReader(p.with_suffix('.pdf')).pages)})
result={'pages':pages,'slides':len(slides),'notes':notes,'native_counts':counts,'assets':assets,'page_text_chars':[len(p.extract_text()) for p in pdf.pages]}
(B/'asset-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
for offset in range(0,pages,6):
    sheet=Image.new('RGB',(1488,1976),'#b8b8b8')
    draw=ImageDraw.Draw(sheet)
    for j in range(6):
        page=offset+j+1
        if page>pages:break
        with Image.open(B/'render-final'/f'page-{page:02d}.png') as im:
            im.thumbnail((730,950))
            x=(j%2)*744+7;y=(j//2)*658+24
            # Each page is scaled to fit a 2 by 3 review grid.
            im.thumbnail((730,626))
            sheet.paste(im,(x,y))
            draw.text((x,y-18),f'PAGE {page}',fill='black')
    sheet.save(B/'render-final'/f'review-{offset+1:02d}.jpg',quality=92)
print(json.dumps({k:result[k] for k in ['pages','slides','notes','native_counts']},ensure_ascii=False))
