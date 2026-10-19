"""Record fixed-snapshot offline review checks with actual Shanghai timestamps."""

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
FULL = "ef24758bd8e9e3e1e8e24760d330a9ffe62af341"
CODE = "696b1d88045ee862db1af3aaf569574ad361feaf"
BASE = "6199ad193d36da17c6597ee286aae40af887d425"
ZONE = ZoneInfo("Asia/Shanghai")
PYTHON = sys.executable


def record(label, argv, cwd=ROOT):
    started = datetime.now(ZONE).isoformat()
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "backend/src")
    result = subprocess.run(argv, cwd=cwd, env=environment, capture_output=True, check=False)
    (RUN / (label + ".stdout.log")).write_bytes(result.stdout)
    (RUN / (label + ".stderr.log")).write_bytes(result.stderr)
    receipt = {"argv": argv, "cwd": str(cwd), "started_at_shanghai": started, "ended_at_shanghai": datetime.now(ZONE).isoformat(), "exit_code": result.returncode, "full_sha": FULL, "code_sha": CODE, "base_sha": BASE, "pythonpath": environment["PYTHONPATH"]}
    (RUN / (label + ".command.json")).write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt))
    print(result.stdout.decode("utf-8", errors="replace")[-9000:])
    print(result.stderr.decode("utf-8", errors="replace")[-2000:])


mode = sys.argv[1]
if mode == "cbm":
    project = "r07-model-fields-review-1-recheck-src"
    operation = sys.argv[2]
    commands = {"index": f"index_repository --repo-path /mnt/d/wt/r07-model-fields-review-1-recheck/backend/src --mode fast --persistence false --name {project}", "schema": f"get_graph_schema --project {project}", "trace": f"trace_path --project {project} --function-name {project}.ai_intel.enrichment.model_fields.generate_model_field_attempts --direction both --format json --depth 4 --limit 100", "generation_trace": f"trace_path --project {project} --function-name {project}.ai_intel.infrastructure.models.generation.GenerationClient.generate --direction both --format json --depth 4 --limit 100"}
    record("cbm_" + operation, ["wsl", "-d", "Ubuntu-22.04", "--", "sh", "-c", "CBM_CACHE_DIR=/tmp/dianzi-cbm-r07-model-fields-review-1-recheck-20261016 CBM_ALLOWED_ROOT=/mnt/d/wt/r07-model-fields-review-1-recheck/backend/src /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli " + commands[operation]])
elif mode == "tests":
    label = sys.argv[2]
    suites = {"original_47": [str(RUN / "test_independent_model_fields.py"), str(RUN / "test_independent_boundary_extra.py")], "new_46": ["tests/unit/test_r07_model_field_root_causes.py"], "original_236": ["tests/unit/test_r07_model_fields.py", "tests/contract/test_r07_model_field_contract.py", "tests/security/test_r07_model_field_security.py", "tests/unit/test_r07_enrichment_contracts.py", "tests/unit/test_t19_structured_enrichment.py", "tests/unit/test_r05_generation.py", "tests/unit/test_r05_generation_review_fixes.py", "tests/contract/test_t18_model_clients.py", "tests/contract/test_t20_claim_extraction.py", "tests/contract/test_t22_research_and_document_links.py", "tests/contract/test_t23_poc_scores_impact.py"], "gateway_independent": [str(RUN / "test_gateway_independent.py")]}
    output_label = sys.argv[3] if len(sys.argv) > 3 else label
    record(output_label, [PYTHON, "-m", "pytest", "-o", "addopts=", "-v", "--import-mode=prepend", *suites[label], "--junitxml=" + str(RUN / (output_label + ".xml"))], ROOT / "backend")
elif mode == "rg":
    record("rg_callers", ["rg", "-n", "generate_model_field_attempts|_require_version_qualifiers|is_atlas_taxonomy|allow_format_repair|max_redirect_hops|def post_json|def request|class PinnedHttpTransport", "backend/src", "backend/tests"])
elif mode == "static":
    files = ["src/ai_intel/enrichment/field_sources.py", "src/ai_intel/enrichment/model_fields.py", "tests/unit/test_r07_model_fields.py", "tests/unit/test_r07_model_field_root_causes.py", "tests/contract/test_r07_model_field_contract.py", "tests/security/test_r07_model_field_security.py"]
    record("ruff", [PYTHON, "-m", "ruff", "check", *files], ROOT / "backend")
    record("format", [PYTHON, "-m", "ruff", "format", "--check", *files], ROOT / "backend")
    record("mypy", [PYTHON, "-m", "mypy", "--config-file", "pyproject.toml", *files[:2]], ROOT / "backend")
    record("source_diff_check", ["git", "diff", "--check", BASE, FULL, "--", "backend/src", "backend/tests"])
    record("package_diff_check", ["git", "diff", "--check", BASE, FULL])
elif mode == "identity":
    record("identity", ["git", "show", "-s", "--format=%H%n%P%n%cI%n%s", "HEAD"])
    record("fixed_code_diff", ["git", "diff", "--exit-code", CODE, FULL, "--", "backend/src", "backend/tests"])
    record("no_source_mutations", ["git", "diff", "--exit-code", FULL, "--", "backend/src", "backend/tests"])
    record("status", ["git", "status", "--short"])
elif mode == "audit":
    record("evidence_audit", [PYTHON, str(RUN / "audit_recheck.py")])
elif mode == "scan":
    sys.path.insert(0, str(ROOT / "scripts"))
    from security_scan import PATTERNS
    paths = [ROOT / path for path in ("backend/src/ai_intel/enrichment/field_sources.py", "backend/src/ai_intel/enrichment/model_fields.py", "backend/tests/unit/test_r07_model_fields.py", "backend/tests/unit/test_r07_model_field_root_causes.py", "backend/tests/contract/test_r07_model_field_contract.py", "backend/tests/security/test_r07_model_field_security.py", "reports/reviews/recovery/G-C-R07-model-fields-review-1-recheck.md")]
    paths += [path for path in RUN.iterdir() if path.is_file()]
    findings = [{"path": str(path.relative_to(ROOT)), "pattern_id": name} for path in paths for name, pattern in PATTERNS.items() if pattern.search(path.read_text(encoding="utf-8", errors="replace"))]
    print(json.dumps({"checked_files": len(paths), "findings": findings}))
    sys.exit(1 if findings else 0)
elif mode == "scan_record":
    record("scope_scan", [PYTHON, str(Path(__file__).resolve()), "scan"])
elif mode == "seal":
    paths = [path for path in RUN.iterdir() if path.is_file() and path.name != "artifact_manifest.json"]
    paths += [ROOT / "reports/reviews/recovery/G-C-R07-model-fields-review-1-recheck.md"]
    artifacts = [{"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(paths)]
    value = {"sealed_at_shanghai": datetime.now(ZONE).isoformat(), "full_sha": FULL, "code_sha": CODE, "base_sha": BASE, "cwd": str(ROOT), "artifacts": artifacts}
    path = RUN / "artifact_manifest.json"
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")
    print(json.dumps({"artifacts": len(artifacts), "manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "sealed_at_shanghai": value["sealed_at_shanghai"]}))
