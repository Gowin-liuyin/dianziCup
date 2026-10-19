from pathlib import Path
import json
from pypdf import PdfReader, PdfWriter
from PIL import Image

root=Path(__file__).resolve().parents[1]
out=root/'deliverables'/'fig'
out.mkdir(exist_ok=True)
order=json.loads((root/'build/slides-order.json').read_text(encoding='utf-8'))
pdf=PdfReader(root/'build/figures-all.pdf')
results=[]
for index, name in enumerate(order):
    if name == 'STYLE': continue
    with Image.open(root/'fig'/f'{name}.png') as image:
        image.save(out/f'{name}.png',dpi=(384,384))
        assert image.width >= 2400
        size=list(image.size)
    writer=PdfWriter();writer.add_page(pdf.pages[index])
    writer.write(out/f'{name}.pdf')
    results.append({'id':name,'size':size,'dpi':384,'vector':f'{name}.pdf'})
(root/'build/figure-assets.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'Exported {len(results)} PNG/PDF pairs, 2400 px wide and 384 dpi')
