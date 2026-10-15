"""Seal exact report/run bytes, source Git blobs and real command/JUnit counts."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from xml.etree import ElementTree

from run_commands import NEW_CONTRACT, NEW_TEST, ROOT, RUN, SOURCE_PATHS, timestamp

BASELINE = "7f8cdc81108e39819d192c09bf1b4a61c640aec9"
CODE = "9df5a61d29ff489e13fb87876e35399ebb9cb00a"
REPORT = ROOT / "reports/tasks/R07-public-signals-fix1.md"
AUTHOR_REPORT = "reports/tasks/R07-public-signals.md"
AUTHOR_RUN = "reports/runs/recovery_r07_public_signals_20261015"
REVIEW_RUN = Path("D:/wt/r07-public-signals-review-1/reports/runs/recovery_r07_public_signals_review_1_20261016")


def git(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=ROOT, text=True).strip()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def exact_blob(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def counts(path: Path) -> dict[str, int]:
    suite = ElementTree.parse(path).getroot().find("testsuite")
    assert suite is not None
    result = {key: int(suite.get(key, "0")) for key in ("tests", "failures", "errors", "skipped")}
    result["passed"] = result["tests"] - result["failures"] - result["errors"] - result["skipped"]
    return result


def prepare_identity() -> None:
    assert git("rev-parse", "HEAD") == CODE
    copied = []
    for name in ("independent_boundaries_v2.log", "independent_boundaries_v2.xml",
                 "independent_boundaries_v2.command.json"):
        source = REVIEW_RUN / name
        target = RUN / ("review_original_" + name)
        target.write_bytes(source.read_bytes())
        copied.append({"source": str(source), "snapshot": target.relative_to(ROOT).as_posix(),
                       "sha256": digest(source.read_bytes()), "exact_bytes_equal": source.read_bytes() == target.read_bytes()})
    source_records = []
    for path in (*SOURCE_PATHS, NEW_TEST, NEW_CONTRACT):
        raw = (ROOT / path).read_bytes()
        committed = subprocess.check_output(["git", "show", CODE + ":" + path], cwd=ROOT)
        source_records.append({"path": path, "working_bytes_sha256": digest(raw),
                               "git_blob": git("rev-parse", CODE + ":" + path),
                               "git_bytes_sha256": digest(committed),
                               "lf_normalized_equals_git": raw.replace(b"\r\n", b"\n") == committed})
    inherited = []
    for path in git("ls-tree", "-r", "--name-only", BASELINE, "--", AUTHOR_REPORT, AUTHOR_RUN).splitlines():
        inherited.append({"path": path, "baseline_git_blob": git("rev-parse", BASELINE + ":" + path),
                          "current_git_blob": git("rev-parse", CODE + ":" + path)})
    assert all(item["baseline_git_blob"] == item["current_git_blob"] for item in inherited)
    source_tree = []
    for line in git("ls-tree", "-r", CODE, "--", "backend/src").splitlines():
        metadata, path = line.split("\t", 1)
        source_tree.append({"path": path, "git_blob": metadata.split()[2],
                            "working_bytes_sha256": digest((ROOT / path).read_bytes())})
    identity = {"sealed_at": timestamp(), "baseline_material_sha": BASELINE,
                "baseline_code_sha": "7142c38620150d5f2b7d81963389bdf8b725c316",
                "business_code_sha": CODE, "branch": git("branch", "--show-current"),
                "worktree": str(ROOT), "source_tree_git_sha": git("rev-parse", CODE + ":backend/src"),
                "source_files": source_records, "source_tree_filelist": source_tree,
                "author_materials_unchanged": inherited, "review_red_originals": copied,
                "review_probe_snapshot_equal": (RUN / "test_independent_boundaries_original.py").read_bytes()
                    == (REVIEW_RUN / "test_independent_boundaries.py").read_bytes(),
                "new_network_calls": 0, "new_model_calls": 0, "pg_calls": 0, "mapping_calls": 0,
                "ponytail_skill": {"path": "C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail/SKILL.md",
                    "sha256": digest(Path("C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail/SKILL.md").read_bytes()),
                    "level": "full"}}
    (RUN / "candidate_identity.json").write_text(json.dumps(identity, indent=2) + "\n", encoding="utf-8")


def seal() -> None:
    assert git("rev-parse", "HEAD") == CODE
    commands = []
    for path in sorted(RUN.glob("*.command.json")):
        if path.name.startswith("review_original_"):
            continue
        record = json.loads(path.read_bytes())
        xml_args = [arg.removeprefix("--junitxml=") for arg in record["argv"] if arg.startswith("--junitxml=")]
        if xml_args:
            record["junit_path"] = xml_args[0]
            record["junit_counts"] = counts(Path(xml_args[0]))
            if record["name"] == "new_regression":
                record["junit_snapshot_note"] = "Early green XML was reused by frozen split-file run; this command's own log is its historical count authority."
        commands.append(record)
    files = []
    for path in sorted((*RUN.rglob("*"), REPORT)):
        if not path.is_file() or path.name == "artifact_manifest.json" or "__pycache__" in path.parts:
            continue
        raw = path.read_bytes()
        files.append({"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
                      "sha256": digest(raw), "git_blob_exact_bytes": exact_blob(raw)})
    manifest = {"sealed_at": timestamp(), "business_code_sha": CODE, "baseline_material_sha": BASELINE,
                "material_commit_reference": "The Git commit containing this manifest and R07-public-signals-fix1.md; supplied to root after commit.",
                "material_files": files, "command_results": commands,
                "filelist_sha256": digest(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()),
                "final_test_counts": {"original_red": counts(RUN / "original_red.xml"),
                                      "focused_frozen": counts(RUN / "focused.xml"),
                                      "regression_frozen": counts(RUN / "regression.xml"),
                                      "original_recheck_frozen": counts(RUN / "original_recheck.xml"),
                                      "new_regression_frozen": counts(RUN / "new_regression.xml")},
                "status": "awaiting_review", "full_pure_inherited": "failed; 1944 passed/1 failed; not rerun or closed",
                "live": "not_run", "cwe_real_catalog": "blocked_live", "new_network_calls": 0,
                "new_model_calls": 0, "pg_calls": 0, "mapping_calls": 0, "raw_public_bodies_copied": False}
    (RUN / "artifact_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"business_code_sha": CODE, "material_files": len(files),
                      "filelist_sha256": manifest["filelist_sha256"], "final_test_counts": manifest["final_test_counts"]}))


if __name__ == "__main__":
    import sys
    prepare_identity() if sys.argv[1] == "identity" else seal()
