"""Archive only the four explicitly frozen evidence packages without overwrites."""

import argparse
import gzip
import hashlib
import io
import json
import pathlib
import subprocess
import sys
import zipfile
from datetime import datetime, timedelta, timezone


ROOT = pathlib.Path("D:/dianzi")
RUN = ROOT / "reports/runs/recovery_evidence_archive_20261016/batch14"
PREVIOUS = "reports/runs/recovery_evidence_archive_20261016/archive_followup_13_priority_receipt.json"
CONFIGS = [
    {
        "id": "A-R17-author", "priority": "A", "root": "D:/wt/r17-sbom-workbench-fix1",
        "fresh_root": "D:/wt/r17-sbom-review1-fix1", "commit": "5587deb124f06b9aa14fb7feb22cdc9493ae4883",
        "run": "reports/runs/recovery_r17_sbom_workbench_fix1_20261016",
        "report": "reports/tasks/R17-sbom-workbench-fix1.md",
        "manifest": "raw_manifest.json", "manifest_sha": "eac16b2332e1a1fb6e11d45999f3ccb6c1836a11d1dbe986c592c11ac5dd16f9",
        "report_sha": "6875f503aee43c40a4df9c00924f92e8f34a30add47dcf805fea47d6002e55ac", "members": 136,
        "supplement": "raw_manifest.sha256", "git_author": True,
    },
    {
        "id": "A-R17-review", "priority": "A", "root": "D:/wt/r17-sbom-review1-fix1",
        "commit": "5587deb124f06b9aa14fb7feb22cdc9493ae4883",
        "run": "reports/runs/recovery_r17_sbom_workbench_review1_fix1_20261016",
        "report": "reports/reviews/recovery/G-E-R17-sbom-workbench-review-1-recheck.md",
        "manifest": "raw_manifest.json", "manifest_sha": "c5e2ea1ad87a6acc7d6d280eb0d841d69234e19991db9d21c874bceb18fa56ac",
        "report_sha": "89cf702908a313736e07cd7dda4772dd3c8029b657c39d5d3f740679e3cfe0f9", "members": 246,
        "supplement": "raw_manifest.sha256", "git_author": False,
    },
    {
        "id": "B-R10-author", "priority": "B", "root": "D:/wt/r10-neo4j-projection-fix2",
        "fresh_root": "D:/wt/r10-neo4j-projection-review1-fix2", "commit": "e8e4086fccc2d9c3f2f582f85e185f5b6f395f0b",
        "run": "reports/runs/recovery_r10_neo4j_projection_fix2_20261016",
        "report": "reports/tasks/R10-neo4j-projection-fix2.md",
        "manifest": "raw_evidence_manifest.json", "manifest_sha": "313ec07323e8aa2ea8e108c1bdbe97b36de4308310cad90c1a89371b43229e47",
        "report_sha": "1f08490f9fb6202bdbf47145c2656ccf66d73b9a8828b048cb4699bb35d18657", "members": 55,
        "supplement": "raw_evidence.zip", "git_author": True,
    },
    {
        "id": "B-R10-review", "priority": "B", "root": "D:/wt/r10-neo4j-projection-review1-fix2",
        "commit": "e8e4086fccc2d9c3f2f582f85e185f5b6f395f0b",
        "run": "reports/runs/recovery_r10_neo4j_projection_review1_fix2_20261016",
        "report": "reports/reviews/recovery/G-C-R10-neo4j-projection-review-1-recheck2.md",
        "manifest": "raw_evidence_manifest.json", "manifest_sha": "489ee1aaeff38fe6f14337e325ce780d58490a5f7b2132506a772bedb4b1f24b",
        "report_sha": "d7a3e3940d9a7cabc5a6cfb9d442d3c0d41d263fc2663d3cee56d3dcaed93b5d", "members": 65,
        "supplement": "raw_evidence.zip", "git_author": False,
    },
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
    if relative != config["report"] and not relative.startswith(config["run"] + "/"):
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
    members = manifest.get("members", manifest.get("files"))
    if len(members) != config["members"]:
        raise ValueError(f"Manifest member count mismatch: {config['id']}")
    paths = [member["path"] for member in members]
    if len(set(paths)) != len(paths):
        raise ValueError(f"Duplicate manifest members: {config['id']}")
    expected = {member["path"]: (member.get("bytes", member.get("length_bytes")),
                                member.get("sha256", member.get("raw_sha256"))) for member in members}
    if config["report"] not in expected:
        report_raw = (source / config["report"]).read_bytes()
        expected[config["report"]] = (len(report_raw), config["report_sha"])
    expected[manifest_relative] = (len(manifest_raw), config["manifest_sha"])
    supplement_relative = config["run"] + "/" + config["supplement"]
    supplement_raw = (source / supplement_relative).read_bytes()
    if config["supplement"].endswith(".sha256"):
        if supplement_raw.decode("ascii").strip() != config["manifest_sha"]:
            raise ValueError(f"Manifest sidecar mismatch: {config['id']}")
    elif sha(supplement_raw) != manifest["archive_sha256"]:
        raise ValueError(f"Raw ZIP SHA mismatch: {config['id']}")
    expected[supplement_relative] = (len(supplement_raw), sha(supplement_raw))
    files = []
    raw_map = {}
    for relative, (length, expected_sha) in expected.items():
        validate_path(config, relative)
        raw = (source / relative).read_bytes()
        if len(raw) != length or sha(raw) != expected_sha:
            raise ValueError(f"Original raw member mismatch: {relative}")
        target = ROOT / relative
        before = identity(target.read_bytes()) if target.exists() else None
        if before is not None and (before["sha256"] != expected_sha or before["size_bytes"] != length):
            raise FileExistsError(f"Canonical conflict, original retained: {relative}")
        row = {"path": relative, "expected_raw_sha256": expected_sha, "source_before": identity(raw),
               "canonical_before": before, "original_manifest_member": relative in paths}
        if config["git_author"]:
            blob = git(str(source), "show", config["commit"] + ":" + relative)
            row["frozen_Git_blob"] = {**identity(blob), "raw_equal": blob == raw,
                                      "lf_normalized_equal": blob == raw.replace(b"\r\n", b"\n")}
            declared_lf = next((member.get("git_lf_sha256") for member in members if member["path"] == relative), None)
            if declared_lf is not None and sha(blob) != declared_lf:
                raise ValueError(f"Declared Git LF mismatch: {relative}")
            fresh_raw = (pathlib.Path(config["fresh_root"]) / relative).read_bytes()
            row["fresh_reviewer_checkout"] = {**identity(fresh_raw), "raw_equal": fresh_raw == raw,
                                              "lf_normalized_equal": fresh_raw.replace(b"\r\n", b"\n") == blob}
            if fresh_raw != raw and fresh_raw.replace(b"\r\n", b"\n") != blob:
                raise ValueError(f"Fresh checkout is neither raw nor matching Git LF: {relative}")
        raw_map[relative] = raw
        files.append(row)
    if sha(raw_map[config["report"]]) != config["report_sha"]:
        raise ValueError(f"Report SHA mismatch: {config['id']}")
    archives = []
    for relative, raw in raw_map.items():
        if relative.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                names = archive.namelist()
                expected_names = set(paths) - {relative}
                if len(names) != len(set(names)) or set(names) != expected_names:
                    raise ValueError(f"Raw ZIP allowlist mismatch: {relative}")
                for entry in archive.infolist():
                    expanded = archive.read(entry)
                    if expanded != raw_map[entry.filename]:
                        raise ValueError(f"Raw ZIP member byte mismatch: {entry.filename}")
                archives.append({"path": relative, **identity(raw), "members": len(names),
                                 "expanded_bytes": sum(entry.file_size for entry in archive.infolist()),
                                 "all_members_match_original_manifest_raw": True})
        elif relative.endswith(".gz"):
            expanded = gzip.decompress(raw)
            archives.append({"path": relative, **identity(raw), "expanded": identity(expanded), "format_modified": False})
    return {"id": config["id"], "source_workspace": str(source), "source_HEAD_observed": observed_head,
            "source_HEAD_not_inferred_as_reviewer_own_commit": not config["git_author"],
            "original_manifest": {"path": manifest_relative, **identity(manifest_raw), "members": len(members)},
            "report": {"path": config["report"], **identity(raw_map[config["report"]]), "in_original_manifest": config["report"] in paths},
            "raw_archives": archives, "files": files, "raw_map": raw_map}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("priority", choices=["A", "B"])
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
    filelist_relative = f"reports/runs/recovery_evidence_archive_20261016/batch14/priority_{arguments.priority}_filelist.tsv"
    write_once(ROOT / filelist_relative, filelist.encode("utf-8"))
    protected_after = {relative: identity((ROOT / relative).read_bytes()) for relative in protected_paths}
    ended = now()
    receipt = {"schema_version": "recovery-frozen-evidence-archive/14", "batch": 14, "priority": arguments.priority,
               "started_at": started, "ended_at": ended, "timezone": "Asia/Shanghai", "argv": sys.argv,
               "role": "frozen byte archive only; no business review or acceptance", "packages": packages,
               "summary": {"canonical_files": len(rows), "copied_new": sum(row['copy_action'] == 'copied_new' for _, row in rows),
                           "reused_identical": sum(row['copy_action'] == 'reused_identical' for _, row in rows),
                           "raw_bytes": sum(row['source_before']['size_bytes'] for _, row in rows),
                           "overwrites": 0, "raw_manifest_mismatch": 0, "raw_zip_member_mismatch": 0,
                           "all_original_sources_unchanged": True, "business_tests": "not_run", "acceptance_signed": False},
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
    main()
