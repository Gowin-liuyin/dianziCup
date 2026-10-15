"""Freeze source and independent evidence hashes, receipts, and observable environment facts."""

import difflib
import hashlib
import importlib.metadata
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
WORKTREE = Path('C:/Users/yinha/.codex/worktrees/recovery-r05-vector-foundation-review-1/dianzi')
BASE = 'fd01ea3e0205361c1f446d6fb97694aa3aa715cf'
FROZEN = '8dd9c73ca4494068e0d83ef5f8db66a1ab409c13'


def git(*arguments: str) -> str:
    result = subprocess.run(['git', *arguments], cwd=WORKTREE, capture_output=True, check=True, text=True, encoding='utf-8')
    return result.stdout.strip()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == '__main__':
    assert git('rev-parse', 'HEAD') == FROZEN
    assert git('status', '--porcelain') == ''
    files = git('diff', '--name-only', BASE, FROZEN).splitlines()
    hashes = {name: digest(WORKTREE / name) for name in files}
    own_files = [path for path in ROOT.glob('*.py') if path.is_file()]
    own_hashes = {path.name: digest(path) for path in own_files}
    v1 = ROOT / 'test_independent_vector_foundation.py'
    v2 = ROOT / 'test_independent_vector_foundation_v2.py'
    adaptation = ''.join(difflib.unified_diff(v1.read_text(encoding='utf-8').splitlines(True),
                                             v2.read_text(encoding='utf-8').splitlines(True),
                                             fromfile=v1.name, tofile=v2.name))
    (ROOT / 'independent_v2.adaptation.diff').write_text(adaptation, encoding='utf-8')
    summaries = {}
    for path in ROOT.glob('*.xml'):
        suites = ET.parse(path).getroot()
        summaries[path.name] = {attribute: sum(int(suite.get(attribute, '0')) for suite in suites.iter('testsuite'))
                                for attribute in ('tests', 'failures', 'errors', 'skipped')}
    from ai_intel.infrastructure.models import clients, semantic
    from ai_intel.retrieval import persistence_models
    origins = {module.__name__: module.__file__ for module in (clients, semantic, persistence_models)}
    assert all(Path(value).is_relative_to(WORKTREE) for value in origins.values())
    data = {
        'recorded_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
        'base_sha': BASE, 'frozen_sha': FROZEN, 'tree': git('rev-parse', 'HEAD^{tree}'),
        'branch': git('branch', '--show-current'), 'worktree': str(WORKTREE), 'status_porcelain': git('status', '--porcelain'),
        'files': hashes, 'independent_evidence_sha256': own_hashes, 'junit': summaries,
        'interpreter': sys.version, 'python_executable': sys.executable, 'source_origins': origins,
        'runtime_versions': {name: importlib.metadata.version(name) for name in ('pgvector', 'sqlalchemy', 'psycopg', 'numpy', 'onnxruntime', 'tokenizers', 'pytest', 'mypy', 'ruff')},
        'upstream_semantic_bytes_diff': git('diff', '--stat', '1e77c0d83a95f22ffd6457c2bb432eb2c0538f9e', FROZEN, '--',
                                         'backend/src/ai_intel/infrastructure/models/semantic.py',
                                         'backend/src/ai_intel/infrastructure/process_limits.py',
                                         'backend/src/ai_intel/ingestion/parsing/_pdf_worker.py'),
    }
    (ROOT / 'recheck_snapshot.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    (ROOT / 'recheck_code.diff').write_text(git('diff', BASE, FROZEN), encoding='utf-8')
    print(json.dumps(data, ensure_ascii=False, indent=2))
