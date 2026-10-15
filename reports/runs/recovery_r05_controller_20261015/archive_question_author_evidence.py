"""按已知作者提交显式导入自有报告，不覆盖任何不同的工作区文件。"""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path(__file__).resolve().parents[3]
run = Path(__file__).resolve().parent
receipt = run / "question_author_evidence_import.json"
assert not receipt.exists()
packages = (
    ("a0fc736576e9cf0c4f0534bc6c060703f75ec121", ("90f0c98d1ca576aed6d1f170b8c4a2070e7912a6", "a0fc736576e9cf0c4f0534bc6c060703f75ec121"), ("reports/runs/recovery_r05_grounded_answer_core_20261015/", "reports/tasks/R05-grounded-answer-core.md")),
    ("444a678b38c148fffdd0d7946ac4f224665e0de2", ("444a678b38c148fffdd0d7946ac4f224665e0de2",), ("reports/runs/recovery_r05_question_frontend_20261015/", "reports/tasks/R05-question-frontend.md")),
    ("11f27b27ed6f5a00708b1ac125e24c37148b842c", ("11f27b27ed6f5a00708b1ac125e24c37148b842c",), ("reports/runs/recovery_r05_question_api_tests_20261015/", "reports/tasks/R05-question-api-tests.md")),
)
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
planned = []
for version, commits, prefixes in packages:
    names = set()
    for commit in commits:
        names.update(subprocess.check_output(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit], cwd=root, text=True).splitlines())
    for name in sorted(names):
        assert any(name.startswith(prefix) for prefix in prefixes), "unexpected author-owned path"
        path = root / name
        assert path.resolve().is_relative_to(root)
        content = subprocess.check_output(["git", "show", version + ":" + name], cwd=root)
        if path.exists():
            assert path.is_file() and path.read_bytes() == content, "existing different file is protected: " + name
        planned.append((name, content, version))
for name, content, version in planned:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(content)
    subprocess.run(["git", "add", "--", name], cwd=root, check=True, capture_output=True)
manifest = [{"path": name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(), "author_evidence_commit": version} for name, content, version in planned]
receipt.write_text(json.dumps({"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "files": manifest, "file_count": len(planned), "bytes": sum(len(content) for _, content, _ in planned)}, indent=2), encoding="utf-8")
print(json.dumps({"explicit_author_files_staged": len(planned), "bytes": sum(len(content) for _, content, _ in planned)}))
