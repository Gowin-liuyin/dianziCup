"""Capture frozen checkout, read contracts and real local commands for this review."""
import hashlib
import json
from pathlib import Path
import subprocess
from review_runner import ROOT, RUN, run

paths = ['AGENTS.md', 'docs/plan/00_execution_map.md', 'docs/decisions/CR-R10_graph_validity.md',
         'docs/decisions/CR-R10_graph_fix2.md', 'progress/task_state.json']
paths += [str(p.relative_to(ROOT)).replace('\\', '/') for p in (ROOT/'docs').rglob('*.md')
          if p.name.startswith(('03', '04', '05', '06', 'R10', 'T17', 'T21', 'T22', 'T23', 'T41'))
          or 'public_api_v2' in p.name or 'master' in p.name]
reading = []
for name in dict.fromkeys(paths):
    path = ROOT/name
    if path.is_file():
        raw = path.read_bytes()
        reading.append({'path': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
(RUN/'contract_read_hashes.json').write_text(json.dumps(reading, indent=2), encoding='utf-8')
run('locked_environment', ['uv', 'sync', '--locked', '--offline'], ROOT/'backend')
run('writer_callers', ['rg', '-n', 'event_documents|attach_evidence_span\(|claim_evidence|claims\.insert|bump_scope_epoch|save_change_publication', 'backend/src'], ROOT)
run('graph_callers', ['rg', '-n', 'validate_field_candidate\(|EvidenceGraphReadService|build_graph_router|r10-graph-1\.', 'backend/src'], ROOT)
run('fixed_source_diff', ['git', 'diff', '--check', '3516b9109b9b7f2c5691d78ad0439aea4a659f4f', '08b141bd437c1de70a8435a1f7f6c448a131ed0d', '--', 'backend', 'docs/decisions/CR-R10_graph_fix2.md'], ROOT)
run('fixed_source_identity', ['git', 'diff', '11d24131aff176cc97f138d2e4a222cd378590d4', '08b141bd437c1de70a8435a1f7f6c448a131ed0d', '--', 'backend/src'], ROOT)
old_unit = subprocess.check_output(['git', 'show', 'b0b7a5b856cc38862f64c01565309564d67c34c0:backend/tests/unit/test_r10_evidence_graph.py'], cwd=ROOT)
(RUN/'test_legacy_unit.py').write_bytes(old_unit)
print('contracts', len(reading), 'old unit bytes', len(old_unit))
