from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import etree

path = Path(__file__).parent / 'figures-draft.pptx'
with ZipFile(path) as archive:
    files = {name: archive.read(name) for name in archive.namelist()}
ns = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main'}
for name, content in files.items():
    if name.startswith('ppt/slides/slide') and name.endswith('.xml'):
        tree = etree.fromstring(content)
        shapes = tree.find('p:cSld/p:spTree', ns)
        connectors = shapes.findall('p:cxnSp', ns)
        for connector in connectors:
            shapes.remove(connector)
        for offset, connector in enumerate(connectors):
            shapes.insert(2 + offset, connector)
        files[name] = etree.tostring(tree, xml_declaration=True, encoding='UTF-8', standalone=True)
with ZipFile(path, 'w', ZIP_DEFLATED) as archive:
    for name, content in files.items():
        archive.writestr(name, content)
print('Native connectors placed behind shape and label fills')
