import json,subprocess
from pathlib import Path
from pypdf import PdfReader,PdfWriter
root=Path('D:/dianzi/output/shaowang-paper-figures-20261016')
r=PdfReader(root/'build/report-insertion-proof.pdf'); w=PdfWriter()
for page in [16,19,32,40,45,61]: w.add_page(r.pages[page-1])
w.write(root/'deliverables/ShaoWang-论文版心插图样张.pdf')
(root/'build/proof-render').mkdir(exist_ok=True)
subprocess.run(['pdftoppm','-png','-scale-to','1700',str(root/'deliverables/ShaoWang-论文版心插图样张.pdf'),str(root/'build/proof-render/page')],check=True)
print('Rendered 6 actual report insertion pages')
