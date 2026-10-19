from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
p=Path('D:/dianzi/output/shaowang-paper-figures-20261016/build')
with ZipFile(p/'redrawn-draft.pptx') as src, ZipFile(p/'unlocked.pptx','w',ZIP_DEFLATED) as dst:
 for name in src.namelist():
  body=src.read(name)
  if name.startswith('ppt/slides/slide') and name.endswith('.xml'):
   body=body.replace(b'noGrp="1"',b'noGrp="0"')
  dst.writestr(name,body)
