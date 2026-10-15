import hashlib
import json
from pathlib import Path
from ai_intel.ingestion.parsing.pdf_text import parse_pdf_text_layer

root = Path('D:/wt/gb-stage-review')
raw = (root / 'docs/references/competition_brief.pdf').read_bytes()
expected = '37f28bc38db91ec0407551b1254c8bc882432a8488ce896c681e1210814c6cf3'
assert hashlib.sha256(raw).hexdigest() == expected
parsed = parse_pdf_text_layer(raw)
assert parsed.status == 'parsed'
assert set(block.page_number for block in parsed.blocks) == {1,2,3,4}
for block in parsed.blocks:
    assert parsed.normalized_text[block.start_offset:block.end_offset] == block.text
report = {'official_pdf_sha256':expected,'status':parsed.status,'parser_version':parsed.parser_version,'characters':len(parsed.normalized_text),'pages':sorted({block.page_number for block in parsed.blocks}),'block_coordinates_exact':True}
(Path(__file__).parent / 'official_pdf.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
