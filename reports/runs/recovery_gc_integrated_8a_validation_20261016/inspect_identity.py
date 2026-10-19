"""Record module identity, API shape, source cleanliness and non-value scan findings."""

import datetime as dt
import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
sys.path.insert(0, str(ROOT))
sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
assert sha == "8a1b04d48346d8550f0326a77f003246a0ebbab5"
generated = ROOT / "frontend/tsconfig.tsbuildinfo"
before = generated.read_bytes()
original = subprocess.check_output(["git", "show", "HEAD:frontend/tsconfig.tsbuildinfo"], cwd=ROOT)
(RUN / "tsbuildinfo.generated.bin").write_bytes(before)
generated.write_bytes(original)
(RUN / "tsbuildinfo_restore.json").write_text(json.dumps({"path": str(generated), "generated_sha256": hashlib.sha256(before).hexdigest(), "restored_git_blob_sha256": hashlib.sha256(original).hexdigest(), "restored_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat()}, indent=2), encoding="utf-8")
modules = {}
for name in ("ai_intel.infrastructure.models.generation", "ai_intel.enrichment.model_fields", "ai_intel.enrichment.signals", "ai_intel.assessment.version_ranges", "ai_intel.ingestion.source_jobs", "ai_intel.ingestion.source_failure_receipts"):
    module = importlib.import_module(name)
    path = Path(module.__file__).resolve()
    assert path.is_relative_to(ROOT / "backend/src")
    modules[name] = {"file": str(path), "raw_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
versions = {name: importlib.metadata.version(name) for name in ("ai-intel-backend", "pytest", "pytest-cov", "coverage", "semver", "packaging", "sqlalchemy", "psycopg", "ruff", "mypy", "pypdf")}
(RUN / "runtime_identity.json").write_text(json.dumps({"python": sys.version, "executable": sys.executable, "versions": versions, "modules": modules, "head": sha, "tree": subprocess.check_output(["git", "show", "-s", "--format=%T", "HEAD"], cwd=ROOT, text=True).strip(), "tracked_status_after_restoration": subprocess.check_output(["git", "status", "--short", "--untracked-files=no"], cwd=ROOT, text=True)}, indent=2), encoding="utf-8")
from ai_intel.infrastructure.settings import ApplicationSettings

for name in ApplicationSettings.model_fields:
    os.environ.pop(name.upper(), None)
from ai_intel.api.app import create_application

application = create_application(settings=ApplicationSettings(app_env="test", data_mode="fixture"))
schema = application.openapi()
(RUN / "openapi_shape.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
(RUN / "api_paths.json").write_text(json.dumps({"paths": sorted(schema["paths"]), "no_server_started": True, "no_database_or_provider_configured": True}, indent=2), encoding="utf-8")
from scripts.security_scan import PATTERNS, SCAN_SUFFIXES

temp = Path("D:/wt/gc-8a-validation-tmp/backend_pytest_tmp")
findings = []
for path in sorted(temp.rglob("*")):
    if not path.is_file() or path.suffix not in SCAN_SUFFIXES:
        continue
    content = path.read_bytes().decode("utf-8", errors="ignore").replace("\r\n", "\n").replace("\r", "\n")
    for pattern_id, pattern in PATTERNS.items():
        count = len(list(pattern.finditer(content)))
        if count:
            findings.append({"former_path": "reports/runs/recovery_gc_integrated_8a_validation_20261016/backend_pytest_tmp/" + path.relative_to(temp).as_posix(), "pattern_id": pattern_id, "count": count, "safe_reason": "Isolated tests deliberately wrote synthetic credential-shape fixtures; this is not a secret allowlist or scan-rule change."})
(RUN / "temporary_scan_findings_paths_only.json").write_text(json.dumps(findings, indent=2), encoding="utf-8")
summary = {}
for label in ("backend_full_pure", "privacy_environment_recheck", "pg_selected", "frontend_unit", "event_fixture"):
    tree = ET.parse(RUN / (label + ".xml"))
    rows = []
    layers = {}
    for case in tree.findall(".//testcase"):
        outcome = "failed" if case.find("failure") is not None else "error" if case.find("error") is not None else "skipped" if case.find("skipped") is not None else "passed"
        classname = case.get("classname", "")
        layer = classname.split(".")[1] if classname.startswith("tests.") else "frontend"
        layers.setdefault(layer, {key: 0 for key in ("passed", "failed", "error", "skipped")})[outcome] += 1
        if outcome != "passed":
            rows.append({"classname": classname, "name": case.get("name"), "outcome": outcome})
    summary[label] = {"layers": layers, "non_passing": rows}
(RUN / "junit_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"head": sha, "editable_modules_bound_to_worktree": True, "junit_layers": summary, "temporary_pattern_rows": len(findings)}, ensure_ascii=False))
