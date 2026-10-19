from pathlib import Path
from ai_intel.ingestion.parsing.pdf_text import parse_pdf_text_layer
source=Path('D:\\wt\\r20-8a-diag\\codex\\r20-8a-cpu-guard-diagnosis\\docs\\references\\competition_brief.pdf')
result=parse_pdf_text_layer(source.read_bytes())
print('PDF_RESULT',result.status,len(result.blocks),sorted({b.page_number for b in result.blocks}),flush=True)
assert result.status=='parsed' and {b.page_number for b in result.blocks}=={1,2,3,4}
