import json,copy
from pathlib import Path
from PIL import Image,ImageChops
from pypdf import PdfReader,PdfWriter,Transformation
from pypdf.generic import RectangleObject
root=Path('D:/dianzi/output/shaowang-paper-figures-20261016')
meta=json.loads((root/'build/bounds.json').read_text(encoding='utf-8-sig'))
reader=PdfReader(root/'build/full-canvas.pdf'); combined=PdfWriter()
for i,row in enumerate(meta):
 im=Image.open(root/f"build/{row['id']}-full.png").convert('RGB')
 bbox=ImageChops.difference(im,Image.new('RGB',im.size,'white')).getbbox()
 box=(max(0,bbox[0]-16),max(0,bbox[1]-16),min(im.width,bbox[2]+16),min(im.height,bbox[3]+16))
 im.crop(box).save(root/f"deliverables/png/{row['id']}.png",dpi=(round((box[2]-box[0])/6.10236),)*2)
 row['crop_pixels']=box;row['paper_width_cm']=15.5
 p=reader.pages[i]; scale=900/2400
 left,top,right,bottom=[v*scale for v in box];height=bottom-top;width=right-left
 p.add_transformation(Transformation().translate(-left,-(630-bottom)))
 p.mediabox=RectangleObject((0,0,width,height));p.cropbox=RectangleObject((0,0,width,height));p.scale_by((15.5/2.54*72)/width)
 w=PdfWriter();w.add_page(p);w.write(root/f"deliverables/pdf/{row['id']}.pdf");combined.add_page(p)
combined.write(root/'deliverables/ShaoWang-论文配图预览.pdf')
(root/'build/figure-metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
print(f'Cropped {len(meta)} PNG and vector PDF figures to paper width 15.5 cm')

