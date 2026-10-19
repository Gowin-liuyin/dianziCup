"""Record exact unchanged shared sources and tests before reusing prior PG observations."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
OLD = "7aeb85ae8277c048fb762dbc705436602cb18f9d"
NEW = "5b3869e4dcdfa16c0ae393cd73acae4cf27efbf9"
changed = subprocess.check_output(
    ["git", "diff", "--name-only", OLD, NEW, "--", "backend/src", "backend/tests", "backend/pyproject.toml", "backend/uv.lock"],
    cwd=ROOT, text=True,
).splitlines()
assert changed == ["backend/src/ai_intel/enrichment/taxonomy_inputs.py", "backend/tests/unit/test_r07_input_capabilities.py"]
resources = json.loads((RUN / "resource_copy_manifest.json").read_text())
paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", NEW, "backend/src"], cwd=ROOT, text=True).splitlines()
paths = [path for path in paths if path != changed[0]]
paths += [item["original_path"] for item in resources["files"]]
paths += ["backend/tests/conftest.py", "backend/pyproject.toml", "backend/uv.lock"]
details = []
for relative in sorted(set(paths)):
    old = subprocess.check_output(["git", "show", OLD + ":" + relative], cwd=ROOT)
    new = subprocess.check_output(["git", "show", NEW + ":" + relative], cwd=ROOT)
    assert old == new
    details.append({"path": relative, "bytes": len(new), "git_bytes_sha256": hashlib.sha256(new).hexdigest(), "unchanged": True})
for item in resources["files"]:
    assert hashlib.sha256((ROOT / item["copy_path"]).read_bytes()).hexdigest() == item["copy_raw_sha256"]
references = ["owned_7aeb85_graph_pg_copies.command.json", "owned_7aeb85_graph_pg_copies_retry.command.json", "owned_7aeb85_publication_pg_copies.command.json", "owned_graph_case_union.json", "resource_copy_manifest.json"]
rg = subprocess.run(["rg", "-n", "taxonomy_inputs|parse_cwe_catalog|parse_atlas_catalog|load_taxonomy", "backend/src/ai_intel/knowledge", "backend/src/ai_intel/enrichment/publication.py", "backend/src/ai_intel/enrichment/field_sources.py"], cwd=ROOT, capture_output=True, text=True)
assert rg.returncode == 1 and not rg.stdout
result = {
    "recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
    "prior_tested_source": OLD, "current_source": NEW,
    "new_execution": False,
    "reason": "Fix3 only changes the bounded taxonomy scalar constructor. Shared field/graph/publication sources, original test bytes, dependencies and resource copies are unchanged; source import search confirms no direct parser dependency in those consumers, combined with the prior CBM/source caller audit.",
    "changed_backend_paths": changed, "all_other_backend_src_git_bytes_unchanged": True,
    "reused_graph_passed_unique": 112, "reused_publication_passed": 34,
    "reference_hashes": [{"path": name, "sha256": hashlib.sha256((RUN / name).read_bytes()).hexdigest()} for name in references],
    "import_search": {"command": rg.args, "cwd": str(ROOT), "exit_code": rg.returncode, "stdout": rg.stdout, "stderr": rg.stderr},
    "unchanged_files": details,
}
(RUN / "fix3_shared_regression_reuse.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"source": NEW, "unchanged_files": len(details), "reused_passed": 146, "new_execution": False}))
