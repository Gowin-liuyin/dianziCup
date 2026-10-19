"""Write the independent review with its actual wall-clock timestamp."""

from pathlib import Path

from review_checks import ROOT, RUN, now

target = ROOT / 'reports/reviews/recovery/G-D-R12-production-migration-review-1.md'
target.parent.mkdir(parents=True, exist_ok=True)
assert not target.exists()
content = (RUN / 'report_template.txt').read_text(encoding='utf-8').replace('{{WRITTEN_AT}}', now())
target.write_text(content, encoding='utf-8', newline='\n')
print('Independent report written to the owned review path.')
