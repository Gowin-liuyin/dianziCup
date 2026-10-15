"""Verify unchanged original probes and the isolated Windows coverage origin."""

import hashlib
import json
import os
from pathlib import Path

from coverage import CoverageData
from review_runner import RUN, TARGET, WT, now


started = now()
original = Path('D:/dianzi/reports/runs/recovery_r04_sources_review_1_20261015/test_independent_boundaries.py')
current = RUN / 'test_independent_boundaries.py'
expected = original.read_text(encoding='utf-8').replace(
    'worktrees/recovery-r04-sources-review-1/dianzi',
    'worktrees/recovery-r04-sources-review-1-recheck/dianzi',
)
assert current.read_text(encoding='utf-8') == expected
coverage_file = RUN / 'pure_unit_fixed.coverage'
coverage_data = CoverageData(basename=str(coverage_file))
coverage_data.read()
measured_files = sorted(coverage_data.measured_files())
prefix = os.path.normcase(str(WT / 'backend/src')) + os.sep
unexpected = [path for path in measured_files if not os.path.normcase(path).startswith(prefix)]
assert not unexpected
coverage = json.loads((RUN / 'pure_unit_fixed.coverage.json').read_text(encoding='utf-8'))
totals = coverage['totals']
assert totals['percent_covered'] >= 60
receipt = {'started_at': started, 'ended_at': now(), 'head': TARGET, 'cwd': str(WT),
    'command': ['D:/dianzi/backend/.venv/Scripts/python.exe', str(Path(__file__))], 'exit_code': 0,
    'original_probe_sha256': hashlib.sha256(original.read_bytes()).hexdigest(),
    'adapted_probe_sha256': hashlib.sha256(current.read_bytes()).hexdigest(),
    'adaptation_only_one_literal_worktree_path': True,
    'coverage_file': str(coverage_file), 'measured_file_count': len(measured_files),
    'unexpected_roots': unexpected, 'raw_coverage_totals': totals,
    'all_coverage_paths': measured_files}
(RUN / 'coverage_and_probe_origin.command.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
print(json.dumps({key: value for key, value in receipt.items() if key != 'all_coverage_paths'}))
