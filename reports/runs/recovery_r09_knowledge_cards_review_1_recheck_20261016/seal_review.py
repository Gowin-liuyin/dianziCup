"""封存新定向复核，不变更旧证据或固定业务代码。"""

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
REPORT = ROOT / "reports/reviews/recovery/G-C-R09-knowledge-cards-review-1-recheck.md"
MANIFEST = RUN / "artifact_manifest.json"
SIDECAR = RUN / "artifact_manifest.sha256"
FIXED = "b5ca278d739feac5dba9ca3e693d538a5a8d475e"
CODE = "dd36cf78c3d15138683d09c12ea867c0055b9674"
EXCLUDED = {MANIFEST.name, SIDECAR.name, *(f"{label}.{suffix}" for label in ("seal_review", "verify_review") for suffix in ("command.json", "stdout.log", "stderr.log"))}


def digest(value):
    return hashlib.sha256(value).hexdigest()


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT)


def validate_inputs():
    assert git("rev-parse", "HEAD").decode().strip() == FIXED
    assert git("diff", "--name-only", "HEAD") == b""
    allowed_report = REPORT.relative_to(ROOT).as_posix()
    allowed_run = RUN.relative_to(ROOT).as_posix() + "/"
    untracked = git("ls-files", "--others", "--exclude-standard").decode().splitlines()
    assert all(path == allowed_report or path.startswith(allowed_run) for path in untracked)
    assert digest((RUN / "test_independent_boundaries.py").read_bytes()) == "76ca4d4064f65bfd08846a6e57a2c4fde087a10d6422d563094b412890058bbf"
    audit = json.loads((RUN / "materials_audit.json").read_bytes())
    for name in ("original_author_90", "combination_129"):
        for item in audit[name]["files"]:
            assert digest((ROOT / item["path"]).read_bytes()) == item["checkout_raw_sha256"]
    for name in ("original_r09_review_121", "shared_generation_review_121"):
        directory = Path(audit[name]["root"])
        for item in audit[name]["files"]:
            assert digest((directory / item["path"]).read_bytes()) == item["raw_sha256"]
    return {"head": FIXED, "code_sha": CODE, "code_tree": audit["code_tree"], "tracked_diff_empty": True, "new_files_ownership_checked": True, "four_input_bundles_unchanged": True, "original_probe_sha256": digest((RUN / "test_independent_boundaries.py").read_bytes())}


if "--verify" in sys.argv:
    validation = validate_inputs()
    expected = SIDECAR.read_text(encoding="ascii").split()[0]
    assert digest(MANIFEST.read_bytes()) == expected
    manifest = json.loads(MANIFEST.read_bytes())
    for item in manifest["files"]:
        assert digest((ROOT / item["path"]).read_bytes()) == item["sha256"]
    print(json.dumps({"verified_members": len(manifest["files"]), "artifact_manifest_sha256": expected, "verdict": manifest["verdict"], **validation}, ensure_ascii=False))
    raise SystemExit(0)

validation = validate_inputs()
assert "**Verdict: Ship" in REPORT.read_text(encoding="utf-8")
validation["report_sha256"] = digest(REPORT.read_bytes())
(RUN / "seal_validation.json").write_bytes((json.dumps(validation, ensure_ascii=False, indent=2) + "\n").encode())
paths = [REPORT, *(path for path in sorted(RUN.iterdir()) if path.is_file() and path.name not in EXCLUDED)]
manifest = {"schema_version": 1, "sealed_at": datetime.now(timezone(timedelta(hours=8))).isoformat(), "material_sha": FIXED, "code_sha": CODE, "code_tree": validation["code_tree"], "verdict": "Ship: public knowledge-card preparation combination only", "must_1": "closed_for_dd36cf78_combination_only", "whole_r09_accepted": False, "external_requests": 0, "real_model_calls": 0, "pg_sessions": 0, "excluded": sorted(EXCLUDED), "excluded_runtime_directories": "venv, caches, pytest temporary directories; only direct run files and this report are sealed", "files": [{"path": path.relative_to(ROOT).as_posix(), "size_bytes": path.stat().st_size, "sha256": digest(path.read_bytes())} for path in paths]}
MANIFEST.write_bytes((json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode())
manifest_digest = digest(MANIFEST.read_bytes())
SIDECAR.write_bytes((manifest_digest + "  artifact_manifest.json\n").encode("ascii"))
print(json.dumps({"sealed_members": len(paths), "artifact_manifest_sha256": manifest_digest, **validation}, ensure_ascii=False))
