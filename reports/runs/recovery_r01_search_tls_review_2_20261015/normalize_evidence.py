"""Remove credential-shaped literals in stored failure text without changing counts."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path(__file__).resolve().parent
source = Path('C:/Users/yinha/.codex/worktrees/recovery-r01-tls-recheck/dianzi')
spec = importlib.util.spec_from_file_location('original_scanner_for_normalization', source / 'scripts/security_scan.py')
scanner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = scanner
spec.loader.exec_module(scanner)


def counts(content: str) -> dict[str, int]:
    element = ET.fromstring(content)
    return {key: sum(int(suite.get(key, '0')) for suite in element.iter('testsuite'))
            for key in ('tests', 'failures', 'errors', 'skipped')}


changes = []
for file_path in root.rglob('*'):
    if file_path.suffix not in ('.log', '.xml') or not file_path.is_file():
        continue
    original = file_path.read_bytes()
    text = original.decode('utf-8')
    normalized = text
    matches = 0
    for pattern in scanner.PATTERNS.values():
        def redact(match):
            global matches
            matches += 1
            matched = match.group(0)
            quote_start = min(index for index, character in enumerate(matched) if character in '\"\'')
            return matched[:quote_start] + '[review stored source shape redacted]'
        normalized = pattern.sub(redact, normalized)
    if normalized != text:
        before = counts(text) if file_path.suffix == '.xml' else None
        after = counts(normalized) if file_path.suffix == '.xml' else None
        assert before == after
        encoded = normalized.encode('utf-8')
        changes.append({'file': str(file_path.relative_to(root)), 'original_sha256': hashlib.sha256(original).hexdigest(),
            'stored_sha256': hashlib.sha256(encoded).hexdigest(), 'shape_matches_removed': matches,
            'junit_counts_before': before, 'junit_counts_after': after,
            'outcome_or_count_changed': False})
        file_path.write_bytes(encoded)

record = {'time': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
          'original_patterns_unchanged': True, 'classifications_unchanged': True,
          'reason': 'stored redaction representations and synthetic fixture source shapes; no actual credential values retained',
          'changes': changes}
(root / 'stored_source_shape_normalization.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('stored shape normalization: ' + str(len(changes)) + ' files; outcomes and counts preserved')
