"""Seal only fix2 materials; compare frozen code, protected objects and real secrets."""

import hashlib
import json
import re
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

from fix_runner import resources

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
BASE = "28a35f16ad1ebe08a49b63126b2c6fc828607333"
SOURCE = (
    "backend/src/ai_intel/knowledge/graph_projection.py",
    "backend/src/ai_intel/knowledge/graph_projection_models.py",
    "backend/src/ai_intel/infrastructure/neo4j_projection.py",
)
TEST = "backend/tests/integration/test_r10_projection_fix2_empty_reads.py"
REPORT = "reports/tasks/R10-neo4j-projection-fix2.md"


def git(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                            text=True, encoding="utf-8", timeout=30, check=True)
    return result.stdout.rstrip()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def tree(ref):
    return dict((name, identity) for identity, name in
                (line.split("\t", 1) for line in git("ls-tree", "-r", ref).splitlines()))


def main():
    code = sys.argv[1]
    git("merge-base", "--is-ancestor", code, "HEAD")
    assert not git("diff", code, "HEAD", "--name-only", "--", *SOURCE, TEST)
    assert not git("diff", "--name-only", "--", *SOURCE, TEST)
    before, after = tree(BASE), tree(code)
    protected = {name: blob for name, blob in before.items() if name != SOURCE[0]}
    actual = {name: after[name] for name in protected}
    assert protected == actual
    proof = {name: {"original_blob": git("rev-parse", BASE + ":" + name),
                    "frozen_blob": git("rev-parse", code + ":" + name),
                    "raw_sha256": sha((ROOT / name).read_bytes()),
                    "git_lf_sha256": sha((ROOT / name).read_bytes().replace(b"\r\n", b"\n"))}
             for name in SOURCE}
    final = json.loads((RUN / "regression_final.json").read_text(encoding="utf-8"))
    assert final["exit_code"] == 0
    assert all(final["source_file_sha256"][name] == proof[name]["raw_sha256"] for name in SOURCE)
    frozen = {"observed_at": datetime.now().astimezone().isoformat(), "code_sha": code,
              "input_materials_sha": BASE, "source": proof,
              "protected_original_path_count": len(protected),
              "protected_tree_sha256_before": sha(json.dumps(protected, sort_keys=True).encode()),
              "protected_tree_sha256_after": sha(json.dumps(actual, sort_keys=True).encode()),
              "final_test_source_matches": True, "accepted": False, "pushed": False}
    (RUN / "frozen_code_verification.json").write_text(json.dumps(frozen, indent=2), encoding="utf-8")
    pg, neo = resources()
    secrets = (pg.password, neo["NEO4J_TEST_PASSWORD"], pg.render_as_string(hide_password=False),
               pg.set(database="test_dianzi_r10_projection_fix2_20261016").render_as_string(hide_password=False))
    paths = [path for path in RUN.rglob("*") if path.is_file() and path.suffix != ".zip"] + [ROOT / REPORT]
    public_guard = re.search(rb'assert url\.database == "([^"]+)"', (RUN / "fix_runner.py").read_bytes())
    assert public_guard is not None
    public_matches = 0
    for path in paths:
        raw = path.read_bytes()
        assert not any(value and len(value) >= 8 and value.encode() in raw for value in secrets)
        if pg.username and len(pg.username) >= 8 and pg.username.encode() in raw:
            assert path == RUN / "fix_runner.py"
            assert pg.username.encode() not in raw.replace(public_guard[1], b"[public identifier]")
            public_matches += raw.count(pg.username.encode())
    (RUN / "final_secret_scan.json").write_text(json.dumps({
        "observed_at": datetime.now().astimezone().isoformat(), "raw_junit_report_files_scanned": len(paths),
        "actual_value_leak_count": 0, "public_fixed_guard_substring_matches": public_matches,
        "secret_values_output": False,
    }, indent=2), encoding="utf-8")
    archive, manifest = RUN / "raw_evidence.zip", RUN / "raw_evidence_manifest.json"
    paths = sorted(path for path in RUN.rglob("*") if path.is_file() and path not in (archive, manifest))
    entries = []
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as opened:
        for path in paths:
            raw = path.read_bytes()
            name = path.relative_to(ROOT).as_posix()
            opened.writestr(name, raw)
            entries.append({"path": name, "length_bytes": len(raw), "raw_sha256": sha(raw),
                            "git_lf_sha256": sha(raw.replace(b"\r\n", b"\n"))})
    record = {"sealed_at": datetime.now().astimezone().isoformat(), "code_sha": code,
              "input_materials_sha": BASE, "files": entries, "archive_sha256": sha(archive.read_bytes()),
              "task_status": "awaiting_review"}
    manifest.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps({"code_sha": code, "secret_findings": 0,
                      "protected_objects": len(protected), "archive_sha256": record["archive_sha256"],
                      "sealed_members": len(entries)}))


if __name__ == "__main__":
    main()
