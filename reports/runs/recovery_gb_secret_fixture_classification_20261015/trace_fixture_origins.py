"""Resolve reviewed source literals without writing or printing unverified values."""

import ast
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
metadata = json.loads((RUN / "unclassified_metadata.json").read_text(encoding="utf-8"))
sources = [
    "reports/runs/recovery_r01_search_tls_review_1_20261015/review_checks.py",
    "reports/runs/recovery_r02_minio_review_1_20261015/native_auth_failure.py",
    "reports/runs/recovery_r02_minio_review_1_20261015/run_review.py",
    "reports/runs/recovery_r02_persistence_review_1_20261015/credential_failure_probe.py",
    "reports/runs/recovery_r02_persistence_review_1_20261015/credential_failure_probe_v2.py",
    "backend/tests/conftest.py",
    "backend/tests/unit/test_r04_source_rate_limits.py",
    "backend/tests/unit/test_r03_network_review_regressions.py",
]
literal_sources = []
snapshots = []
for relative in sources:
    path = ROOT / relative
    raw = path.read_bytes()
    content = raw.decode("utf-8",errors="ignore")
    snapshots.append({"path":relative,"sha256":hashlib.sha256(raw).hexdigest(),"observed_at":datetime.now(timezone.utc).isoformat(),"blob_sha":subprocess.check_output(["git","hash-object","--",relative],cwd=ROOT,text=True).strip()})
    for node in ast.walk(ast.parse(content)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            literal_sources.append((node.value, relative, node.lineno))
resolved = []
for item in metadata["occurrences"]:
    if "/venv/" in item["path"]:
        continue
    raw = (ROOT / item["path"]).read_bytes()
    content = raw.decode("utf-8",errors="ignore").replace("\r\n","\n").replace("\r","\n")
    span = content[item["start"]:item["end"]]
    quote_start = min(index for index, character in enumerate(span) if character in "\"'")
    value = span[quote_start+1:-1]
    matches = [{"source_path":relative,"source_line":line} for literal,relative,line in literal_sources if literal == value]
    if item["path"].endswith((".py",".ts")):
        matches.append({"source_path":item["path"],"source_line":item["line"]})
    resolved.append({key:item[key] for key in ("path","pattern_id","start","end","line","raw_sha256","match_sha256")} | {"literal_origins":matches})
result={"recorded_at":datetime.now(timezone.utc).isoformat(),"head":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),"source_snapshots":snapshots,"resolutions":resolved}
(RUN / "origin_resolution.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
for item in resolved:
    print(json.dumps({"path":item["path"],"line":item["line"],"literal_origins":item["literal_origins"]},ensure_ascii=False))
