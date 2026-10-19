"""Copy the proved controlled-run harness without copying any old receipt or secret."""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
OLD = RUN.parent / "recovery_r06_document_live_20261015"
ROOT = Path("D:/wt/r06-integrated-live-1156")
SHA = "1156b2ed6616e3a4297215c2893d2cbe633f5215"
replacements = {
    "D:/wt/r06-document-live-0a45185": str(ROOT),
    "recovery_r06_document_live_20261015": RUN.name,
    "0a45185ae3ffb73a6d186b98421e26a52f78bfc6": SHA,
    "r06_document_live_0a45185": "r06_integrated_live_1156",
    "test_dianzi_r06_documents_live_20261015": "test_dianzi_r06_integrated_live_20261015",
    "28011": "28012",
    "25174": "25175",
    "-r06-doc-admin": "-r06-integrated-admin",
    "-r06-doc-viewer": "-r06-integrated-viewer",
    "document-live-viewer": "integrated-live-viewer",
    "R06-document-live.md": "R06-integrated-live.md",
    "D:/dianzi/backend/.venv/Scripts/python.exe": str(ROOT / "backend/.venv/Scripts/python.exe"),
}
files = []
for name in ("prepare.py", "supervise.py", "launch.ps1", "runtime_entry.py", "scan_secrets.py", "scan_secrets.ps1"):
    target = RUN / name
    assert not target.exists(), name
    content = (OLD / name).read_text(encoding="utf-8-sig")
    for before, after in replacements.items():
        content = content.replace(before, after)
    if name == "supervise.py":
        content = content.replace('== 13 and', '== 14 and').replace('"redis_database": 13', '"redis_database": 14')
        content = content.replace('"source_job_budget": 40', '"source_job_budget": 80').replace('stats["jobs"] >= 40', 'stats["jobs"] >= 80')
        content = content.replace('"source_attempt_budget": 120', '"source_attempt_budget": 160').replace('stats["attempts"] >= 120', 'stats["attempts"] >= 160')
    if name == "launch.ps1":
        content = content.replace("'/13'", "'/14'")
        content = content.replace(';D:/dianzi/reports/runs/recovery_gb_controlled_collection_20261015', '')
        content = content.replace("'ANTHROPIC_API_KEY')", "'ANTHROPIC_API_KEY','SOURCE_POLLING_ENABLED')", 1)
        content = content.replace("$env:API_PROXY_TARGET =", "$env:SOURCE_POLLING_ENABLED = 'true'\n    $env:API_PROXY_TARGET =")
        content = content.replace("'document-live.spec.cjs'", "'integrated-live.spec.cjs'")
        content = content.replace('bounded authenticated document collection', 'bounded actual default beat collection')
    target.write_text(content, encoding="utf-8")
    files.append(name)
(RUN / "runtime_limits.py").write_bytes((RUN.parent / "recovery_gb_controlled_collection_20261015/runtime_limits.py").read_bytes())
files.append("runtime_limits.py")
(RUN / "bootstrap_receipt.json").write_text(json.dumps({
    "created_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    "code_sha": SHA, "worktree": str(ROOT), "harness_reused_from": OLD.name,
    "copied_only_scripts": files, "old_receipts_or_response_bodies_copied": False,
    "state": "preparing; external collection not started; awaits root regression gate",
}, indent=2) + "\n", encoding="utf-8")
print("isolated harness scripts copied; no external collection started")
