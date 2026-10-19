"""Archive only the four explicitly frozen evidence packages without overwrites."""

import argparse
import gzip
import hashlib
import io
import json
import pathlib
import subprocess
import sys
import tarfile
import zipfile
from datetime import datetime, timedelta, timezone


ROOT = pathlib.Path("D:/dianzi")
RUN = ROOT / "reports/runs/recovery_evidence_archive_20261016/batch15"
PREVIOUS = "reports/runs/recovery_evidence_archive_20261016/batch14/batch14_index_receipt.json"
CONFIGS = [
    {"id": "C-R11-author", "priority": "C", "root": "D:/wt/r11-sbom-locator-privacy-fix1",
     "fresh_root": "D:/wt/r11-integrated-api-review1-fix1", "commit": "54f17c9a61d55af5ffe43e58d9252efad6317646",
     "run": "reports/runs/recovery_r11_sbom_locator_privacy_fix1_20261016", "report": "reports/tasks/R11-sbom-locator-privacy-fix1.md",
     "reports": ["reports/tasks/R11-sbom-locator-privacy-fix1.md"], "manifest": "artifact_manifest.json", "member_key": "entries",
     "manifest_sha": "39feefefb9c3884b911f4c50ed442276a26256f1c3b015a504fbf49ca3c30cfe", "members": 188,
     "report_sha": "fc711954f276b0d16676249991bb90a8f800c3c058635047d44a1a1d64ed2684", "git_author": True,
     "excluded_business_members": ["backend/src/ai_intel/assets/sbom_inventory.py", "backend/tests/unit/test_r11_sbom_locator_privacy.py"], "supplements": []},
    {"id": "C-R11-review", "priority": "C", "root": "D:/wt/r11-integrated-api-review1-fix1",
     "commit": "54f17c9a61d55af5ffe43e58d9252efad6317646", "run": "reports/runs/recovery_r11_integrated_api_migrations_review1_fix1_20261016",
     "report": "reports/reviews/recovery/G-D-R11-integrated-api-migrations-review-1-recheck.md",
     "reports": ["reports/reviews/recovery/G-D-R11-integrated-api-migrations-review-1-recheck.md"], "manifest": "review_manifest.json", "member_key": "members",
     "manifest_sha": "583f2188448c18f22d41d75853c3262a72739d77702082e316777ea6e89b6540", "members": 122,
     "report_sha": "58cf83cf49af5fbe35e5b034431ffa6e7ddd3bd8c1c40cf5136cae13ac36ffe0", "git_author": False, "excluded_business_members": [], "supplements": []},
    {"id": "D-R18-author", "priority": "D", "root": "D:/wt/r18-sdk-client-fix1", "fresh_root": "D:/wt/r18-sdk-client-review1-fix1",
     "commit": "0601f469f1a90b9061ca77f718aa845051e76641", "run": "reports/runs/recovery_r18_sdk_client_fix1_20261016",
     "report": "reports/tasks/R18-sdk-client-fix1-material-repair.md",
     "reports": ["reports/tasks/R18-sdk-client-fix1.md", "reports/tasks/R18-sdk-client-fix1-material-repair.md"],
     "manifest": "artifact_manifest_material_repair.json", "member_key": "files",
     "manifest_sha": "33c4f94a47e771408f5bf724d67135810a72a09857b89722502ae2118b78ff81", "manifest_git_sha": "86f2ef7091b87f3173a80c85797f66ba95e4dc082596954a92aed54562e3a189", "members": 144,
     "report_sha": "975d055fb5d9ebd0e5d9dae0d71971ffb9915689968da9503555744f88796257", "git_author": True, "excluded_business_members": [],
     "supplements": [{"name": "fresh_material_checkout_byte_proof.json", "sha256": "9d7db9b1996596ee96fc414aa5d23c4f1a0b9b3e9b7dfcd39de5b5555fb34c92", "frozen_commit_member": False}]},
    {"id": "D-R18-review", "priority": "D", "root": "D:/wt/r18-sdk-client-review1-fix1", "commit": "0601f469f1a90b9061ca77f718aa845051e76641",
     "run": "reports/runs/recovery_r18_sdk_cli_review1_fix1_20261016", "report": "reports/reviews/recovery/G-E-R18-sdk-cli-review-1-recheck.md",
     "reports": ["reports/reviews/recovery/G-E-R18-sdk-cli-review-1-recheck.md"], "manifest": "artifact_manifest.json", "member_key": "artifacts",
     "manifest_sha": "5a0b18aaf88d7483bc1d6bc1b259e13a33f0669b087c9ca6e189974794f73094", "members": 57,
     "report_sha": "c05810c05030c700c487815b679550060e3773fde8a7a795830a44be55afc7fe", "git_author": False, "excluded_business_members": [], "supplements": []},
]


def now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="microseconds")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def identity(raw: bytes) -> dict[str, object]:
    return {"size_bytes": len(raw), "sha256": sha(raw), "crlf_count": raw.count(b"\r\n"),
            "lf_normalized_sha256": sha(raw.replace(b"\r\n", b"\n"))}


def git(root: str, *arguments: str) -> bytes:
    result = subprocess.run(["git", "-C", root, *arguments], capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(f"Read-only Git command failed ({result.returncode}): {arguments}")
    return result.stdout


def validate_path(config: dict, relative: str) -> None:
    path = pathlib.PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or "\\" in relative:
        raise ValueError(f"Unsafe manifest path: {relative}")
    if relative not in config["reports"] and relative not in config["excluded_business_members"] and not relative.startswith(config["run"] + "/"):
        raise ValueError(f"Path outside exact package: {relative}")
    if any(part.casefold() in {".git", ".env", "holdout", "dpapi", "keys"} for part in path.parts):
        raise ValueError(f"Forbidden manifest path: {relative}")


def write_once(path: pathlib.Path, raw: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as destination:
            destination.write(raw)
    except FileExistsError:
        if path.read_bytes() != raw:
            raise FileExistsError(f"Canonical conflict, original retained: {path}")
        return "reused_identical"
    return "copied_new"


def prepare(config: dict) -> dict:
    source = pathlib.Path(config["root"])
    observed_head = git(str(source), "rev-parse", "HEAD").decode().strip()
    if observed_head != config["commit"]:
        raise ValueError(f"Source HEAD drift: {config['id']}")
    manifest_relative = config["run"] + "/" + config["manifest"]
    manifest_raw = (source / manifest_relative).read_bytes()
    if sha(manifest_raw) != config["manifest_sha"]:
        raise ValueError(f"Manifest SHA mismatch: {config['id']}")
    manifest = json.loads(manifest_raw)
    members = manifest[config["member_key"]]
    if len(members) != config["members"]:
        raise ValueError(f"Manifest member count mismatch: {config['id']}")
    paths = [member["path"] for member in members]
    if len(set(paths)) != len(paths):
        raise ValueError(f"Duplicate manifest members: {config['id']}")
    expected = {member["path"]: (member.get("bytes", member.get("size_bytes")), member.get("sha256", member.get("raw_sha256"))) for member in members}
    if config["report"] not in expected:
        report_raw = (source / config["report"]).read_bytes()
        expected[config["report"]] = (len(report_raw), config["report_sha"])
    expected[manifest_relative] = (len(manifest_raw), config["manifest_sha"])
    supplements = {}
    for supplement in config["supplements"]:
        relative = config["run"] + "/" + supplement["name"]
        raw = (source / relative).read_bytes()
        if sha(raw) != supplement["sha256"]:
            raise ValueError(f"Explicit appendix SHA mismatch: {relative}")
        expected[relative] = (len(raw), supplement["sha256"])
        supplements[relative] = supplement
    files = []
    excluded = []
    raw_map = {}
    for relative, (length, expected_sha) in expected.items():
        validate_path(config, relative)
        raw = (source / relative).read_bytes()
        if len(raw) != length or sha(raw) != expected_sha:
            raise ValueError(f"Original raw member mismatch: {relative}")
        business_excluded = relative in config["excluded_business_members"]
        target = ROOT / relative
        before = identity(target.read_bytes()) if target.exists() else None
        if not business_excluded and before is not None and (before["sha256"] != expected_sha or before["size_bytes"] != length):
            raise FileExistsError(f"Canonical conflict, original retained: {relative}")
        row = {"path": relative, "expected_raw_sha256": expected_sha, "source_before": identity(raw), "canonical_before": before, "original_manifest_member": relative in paths}
        declared_mode = next((member.get("git_byte_mode") for member in members if member["path"] == relative), None)
        if declared_mode is not None:
            row["declared_Git_byte_mode"] = declared_mode
        committed = relative not in supplements or supplements[relative]["frozen_commit_member"]
        if config["git_author"] and committed:
            blob = git(str(source), "show", config["commit"] + ":" + relative)
            row["frozen_Git_blob"] = {**identity(blob), "raw_equal": blob == raw, "lf_normalized_equal": blob == raw.replace(b"\r\n", b"\n")}
            if declared_mode == "exact_raw" and blob != raw:
                raise ValueError(f"Declared exact_raw Git mismatch: {relative}")
            if declared_mode == "LF" and blob != raw.replace(b"\r\n", b"\n"):
                raise ValueError(f"Declared LF Git mismatch: {relative}")
            if relative == manifest_relative and config.get("manifest_git_sha") and sha(blob) != config["manifest_git_sha"]:
                raise ValueError(f"Declared manifest Git LF mismatch: {relative}")
            fresh_raw = (pathlib.Path(config["fresh_root"]) / relative).read_bytes()
            row["fresh_reviewer_checkout"] = {**identity(fresh_raw), "raw_equal": fresh_raw == raw, "lf_normalized_equal": fresh_raw.replace(b"\r\n", b"\n") == blob.replace(b"\r\n", b"\n")}
            if declared_mode == "exact_raw" and fresh_raw != raw:
                raise ValueError(f"Fresh exact_raw checkout mismatch: {relative}")
            if fresh_raw != raw and fresh_raw.replace(b"\r\n", b"\n") != blob.replace(b"\r\n", b"\n"):
                raise ValueError(f"Fresh checkout is neither raw nor matching Git LF: {relative}")
        elif relative in supplements:
            row["explicit_post_final_appendix"] = {"frozen_commit_member": False, "recursively_followed_references": False}
        raw_map[relative] = raw
        if business_excluded:
            row["copy_action"] = "policy_excluded_business_path_readonly"
            excluded.append(row)
        else:
            files.append(row)
    if sha(raw_map[config["report"]]) != config["report_sha"]:
        raise ValueError(f"Report SHA mismatch: {config['id']}")
    archives = []
    for relative, raw in raw_map.items():
        if relative.endswith(".tar.gz"):
            with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
                entries = archive.getmembers()
                names = [entry.name for entry in entries]
                if len(names) != len(set(names)) or set(names) != set(paths) - {relative} or any(not entry.isfile() for entry in entries):
                    raise ValueError(f"Raw TAR allowlist mismatch: {relative}")
                for entry in entries:
                    if archive.extractfile(entry).read() != raw_map[entry.name]:
                        raise ValueError(f"Raw TAR member byte mismatch: {entry.name}")
                archives.append({"path": relative, **identity(raw), "members": len(names), "expanded_bytes": sum(entry.size for entry in entries), "all_members_match_original_manifest_raw": True, "business_members_preserved_inside_original_archive": len(excluded), "format_modified": False})
    byte_modes = {mode: sum(member.get("git_byte_mode") == mode for member in members) for mode in ["exact_raw", "LF"]}
    if config["id"] == "D-R18-author":
        if byte_modes != {"exact_raw": 71, "LF": 73}:
            raise ValueError("SDK active manifest 71/73 declared modes differ")
        proof = json.loads(raw_map[config["run"] + "/fresh_material_checkout_byte_proof.json"])
        if proof["material_sha"] != config["commit"] or proof["manifest_raw_sha256"] != config["manifest_sha"] or proof["manifest_git_blob_sha256"] != config["manifest_git_sha"]:
            raise ValueError("Explicit post-final declaration identity mismatch")
        if {row["path"] for row in proof["files"]} != set(paths) or len(proof["files"]) != len(paths):
            raise ValueError("Post-final declaration member scope differs")
        by_path = {row["path"]: row for row in files}
        for declaration in proof["files"]:
            actual = by_path[declaration["path"]]
            if declaration["original_raw_sha256"] != actual["source_before"]["sha256"] or declaration["git_blob_sha256"] != actual["frozen_Git_blob"]["sha256"] or declaration["mode"] != actual["declared_Git_byte_mode"]:
                raise ValueError(f"Post-final declaration raw/Git identity mismatch: {declaration['path']}")
    return {"id": config["id"], "source_workspace": str(source), "source_HEAD_observed": observed_head, "source_HEAD_not_inferred_as_reviewer_own_commit": not config["git_author"], "original_manifest": {"path": manifest_relative, **identity(manifest_raw), "members": len(members)}, "report": {"path": config["report"], **identity(raw_map[config["report"]]), "in_original_manifest": config["report"] in paths}, "declared_Git_byte_modes": byte_modes, "raw_archives": archives, "files": files, "excluded_business_members": excluded, "raw_map": raw_map}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("priority", choices=["C", "D"])
    arguments = parser.parse_args()
    started = now()
    protected_paths = [".gitattributes", "frontend/tsconfig.tsbuildinfo", PREVIOUS]
    protected_before = {relative: identity((ROOT / relative).read_bytes()) for relative in protected_paths}
    main_before = git(str(ROOT), "rev-parse", "HEAD").decode().strip()
    packages = [prepare(config) for config in CONFIGS if config["priority"] == arguments.priority]
    rows = []
    for package in packages:
        for row in package["files"]:
            row["copy_action"] = write_once(ROOT / row["path"], package["raw_map"][row["path"]])
        for row in package["files"]:
            source_after = (pathlib.Path(package["source_workspace"]) / row["path"]).read_bytes()
            canonical_after = (ROOT / row["path"]).read_bytes()
            row["source_after"] = identity(source_after)
            row["canonical_after"] = identity(canonical_after)
            if source_after != package["raw_map"][row["path"]] or canonical_after != source_after:
                raise ValueError(f"Postcopy raw drift: {row['path']}")
            row["original_source_unchanged"] = True
            rows.append((package["id"], row))
        for row in package["excluded_business_members"]:
            row["source_after"] = identity((pathlib.Path(package["source_workspace"]) / row["path"]).read_bytes())
            row["canonical_after_readonly_observed"] = identity((ROOT / row["path"]).read_bytes()) if (ROOT / row["path"]).exists() else None
            if row["source_after"] != row["source_before"]:
                raise ValueError(f"Readonly excluded source drift: {row['path']}")
            row["original_source_unchanged"] = True
            row["canonical_business_file_written"] = False
        del package["raw_map"]
        package["summary"] = {"canonical_files": len(package["files"]),
                              "copied_new": sum(row["copy_action"] == "copied_new" for row in package["files"]),
                              "reused_identical": sum(row["copy_action"] == "reused_identical" for row in package["files"]),
                              "raw_bytes": sum(row["source_before"]["size_bytes"] for row in package["files"]),
                              "overwrites": 0, "all_original_sources_unchanged": True,
                              "raw_crlf_files": sum(row["source_before"]["crlf_count"] > 0 for row in package["files"])}
    attrs = [{"package": package_id, "path": row["path"], **row["source_before"], "rule_changes": 0}
             for package_id, row in rows if row["path"].endswith("/.gitattributes")]
    filelist = "package\tpath\tsize_bytes\tsha256\taction\n" + "".join(
        f"{package_id}\t{row['path']}\t{row['source_before']['size_bytes']}\t{row['expected_raw_sha256']}\t{row['copy_action']}\n"
        for package_id, row in rows)
    filelist_relative = f"reports/runs/recovery_evidence_archive_20261016/batch15/priority_{arguments.priority}_filelist.tsv"
    write_once(ROOT / filelist_relative, filelist.encode("utf-8"))
    protected_after = {relative: identity((ROOT / relative).read_bytes()) for relative in protected_paths}
    ended = now()
    receipt = {"schema_version": "recovery-frozen-evidence-archive/15", "batch": 15, "priority": arguments.priority,
               "started_at": started, "ended_at": ended, "timezone": "Asia/Shanghai", "argv": sys.argv,
               "role": "frozen byte archive only; no business review or acceptance", "packages": packages,
               "summary": {"canonical_files": len(rows), "copied_new": sum(row['copy_action'] == 'copied_new' for _, row in rows),
                           "reused_identical": sum(row['copy_action'] == 'reused_identical' for _, row in rows),
                           "raw_bytes": sum(row['source_before']['size_bytes'] for _, row in rows),
                           "overwrites": 0, "raw_manifest_mismatch": 0, "raw_archive_member_mismatch": 0,
                           "all_original_sources_unchanged": True, "excluded_business_members_readonly": sum(len(package["excluded_business_members"]) for package in packages), "business_tests": "not_run", "acceptance_signed": False},
               "main_HEAD_before": main_before, "main_HEAD_after_readonly_observed": git(str(ROOT), "rev-parse", "HEAD").decode().strip(),
               "protected_before": protected_before, "protected_after": protected_after,
               "protected_observed_unchanged": {relative: protected_before[relative] == protected_after[relative] for relative in protected_paths},
               "run_local_attrs_exact_original_bytes_root_authorized": attrs, "root_attrs_rule_changes": 0,
               "filelist": {"path": filelist_relative, **identity(filelist.encode('utf-8')), "rows": len(rows)},
               "execution_limits": {"network": 0, "paid_API": 0, "business_scripts_executed": 0, "source_seal_scripts_executed": 0,
                                    "private_secret_env_holdout_DPAPI_bytes_read": 0, "whole_historical_inventory_rechecked": False,
                                    "Git_index_commit_push_mutations": 0, "product_progress_state_mutations": 0, "subagents_spawned": 0}}
    receipt_path = RUN / f"priority_{arguments.priority}_receipt.json"
    receipt_raw = (json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    write_once(receipt_path, receipt_raw)
    write_once(receipt_path.with_suffix(".sha256"), (sha(receipt_raw) + "\n").encode("ascii"))
    print(json.dumps({"receipt": str(receipt_path), "receipt_sha256": sha(receipt_raw), "summary": receipt["summary"],
                      "per_package": [{"id": package["id"], **package["summary"]} for package in packages],
                      "protected_observed_unchanged": receipt["protected_observed_unchanged"], "started_at": started, "ended_at": ended}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        failure = {"observed_failure_at": now(), "argv": sys.argv, "failure_type": type(error).__name__, "failure": str(error), "overwrites": 0, "original_manifests_modified": False}
        write_once(RUN / f"priority_{sys.argv[-1]}_attempt_failure.json", (json.dumps(failure, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        raise
