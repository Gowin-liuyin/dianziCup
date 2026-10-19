"""最终源码、旧封存包和执行XML实核；冻结LF源码副本与raw证据分列。"""

import gzip
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from review_runner_final import OLD_RUN, ROOT, RUN, now

CODE = "6942c65efd5df013c077275cbb6d8cfec3585080"
MATERIAL = "5be873ec38a41955b5a58e9762df4b866a7a9d63"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout


def main():
    started = now()
    old_raw = (OLD_RUN / "artifact_manifest.json").read_bytes()
    assert sha(old_raw) == "0cc00f729e88152ccf4f527f6861f21c19709be303c8e73bd30844414a77f5a7"
    old = json.loads(old_raw)
    for entry in old["entries"]:
        assert sha((OLD_RUN.parents[2] / entry["path"]).read_bytes()) == entry["sha256"]
    changes = git("diff", "--name-only", "c0369e6b", CODE).decode().splitlines()
    kept = [
        "backend/src/ai_intel/assets/sbom_parser.py", "backend/src/ai_intel/assets/manifest_parser.py",
        "backend/src/ai_intel/assets/inventory_models.py", "backend/src/ai_intel/assets/sbom_persistence_models.py",
        "backend/src/ai_intel/assets/inventory_routes.py", "backend/src/ai_intel/assets/inventory_contracts.py",
        "backend/src/ai_intel/infrastructure/models/json_output.py", "backend/tests/conftest.py",
        "backend/pyproject.toml", "backend/uv.lock", "progress/task_state.json",
    ]
    output = RUN / "final_source_blobs"
    output.mkdir(exist_ok=True)
    sources = []
    for index, name in enumerate(changes + kept):
        raw = git("show", CODE + ":" + name)
        if name in kept:
            assert raw == git("show", "c0369e6b:" + name)
        expected_blob = git("rev-parse", CODE + ":" + name).decode().strip()
        actual_blob = git("hash-object", "--path=" + name, name).decode().strip()
        assert expected_blob == actual_blob
        target = output / (f"{index:02d}_" + Path(name).name + ".gz")
        target.write_bytes(gzip.compress(raw, mtime=0))
        sources.append({"path": name, "git_lf_sha256": sha(raw), "raw_sha256": sha((ROOT / name).read_bytes()), "git_blob": actual_blob, "unchanged_from_c036": name in kept, "blob_copy": target.relative_to(ROOT).as_posix()})
    assert git("rev-parse", "0532c4f5:backend/src/ai_intel/assets/sbom_persistence_models.py") == git("rev-parse", CODE + ":backend/src/ai_intel/assets/sbom_persistence_models.py")
    for path in ("backend/tests/unit/test_r11_sbom_inventory_uri_privacy.py", "backend/tests/integration/test_r11_sbom_inventory_uri_privacy.py", "backend/src/ai_intel/assets/sbom_inventory_contracts.py"):
        assert git("rev-parse", "b4e26971:" + path) == git("rev-parse", CODE + ":" + path)
    summary = {}
    for name in ("pure", "pg_sbom", "pg_legacy", "pg_old", "pg_new", "pg_corrected", "pg_nullmeta", "pure_final", "pg_sbomfinal", "pg_legacyfinal", "pg_oldfinal", "pg_newfinal", "pg_edgesfinal", "pg_edgescorrected"):
        cases = list(ET.parse(RUN / (name + ".xml")).getroot().iter("testcase"))
        count = {kind: sum(case.find(kind) is not None for case in cases) for kind in ("failure", "error", "skipped")}
        count.update(tests=len(cases), passed=len(cases) - sum(count.values()))
        count["groups"] = {group: sum(group in case.attrib.get("classname", "") for case in cases) for group in ("unit", "contract", "security")}
        summary[name] = count
    for name in ("pure_final", "pg_sbomfinal", "pg_legacyfinal", "pg_oldfinal", "pg_newfinal", "pg_edgescorrected"):
        assert not any(summary[name][key] for key in ("failure", "error", "skipped"))
    measurements = (RUN / "sql_capacity_measurements.json").read_bytes()
    (RUN / "sql_capacity_measurements_final.json").write_bytes(measurements)
    receipt = {"start": started, "end": now(), "code_commit": CODE, "material_commit": MATERIAL,
               "current_head": git("rev-parse", "HEAD").decode().strip(), "old_verified_entries": len(old["entries"]),
               "old_manifest_sha256": sha(old_raw), "changed_paths": changes, "sources": sources, "independent_junit": summary,
               "final_sql_measurements_sha256": sha(measurements), "raw_paths_do_not_prove_http_sla": True}
    (RUN / "final_source_audit.json").write_bytes(json.dumps(receipt, indent=2, ensure_ascii=False).encode())
    print(json.dumps({"code": CODE, "old_verified_entries": len(old["entries"]), "junit": summary}, indent=2))


if __name__ == "__main__":
    main()
