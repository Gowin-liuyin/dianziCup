"""Copy an explicit frozen evidence package, preserving existing canonical bytes."""

import argparse
import hashlib
import io
import json
import pathlib
import subprocess
import tarfile
import zipfile
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path("D:/dianzi")
RUN = ROOT / "reports/runs/recovery_evidence_archive_20261016/batch16"
CONFIG = [
    ("A-author", "r07-input-audit-fix1", "648c71795e1bea34511ec0d04348f35f6463a5e6", "recovery_r07_input_audit_fix1_20261016", "raw_manifest.json", "50c03a99", "materials", "changed_source", None, True),
    ("A-review", "r07-input-audit-review1-fix1", "648c71795e1bea34511ec0d04348f35f6463a5e6", "recovery_r07_input_audit_review1_fix1_20261016", "recheck_manifest.json", "51670d15d0cfcf87708fb933ce7df568f234ac34290ac48d9e8e132e3559cf30", "files", None, None, False),
    ("B-author", "r12-conversation-context-fix1", "eb030458009812ec037928e4bc2f1a4cdbe64c46", "recovery_r12_conversation_context_fix1_20261016", "material_manifest.json", "f49a078", None, None, None, True),
    ("B-review", "r12-conversation-context-review1-fix1", "077026f41bd89a1f2ef2293baf017ac1b0dd0772", "recovery_r12_conversation_context_review1_fix1_20261016", "raw_manifest.json", "52419c8", None, None, None, True),
    ("C-author", "r07-r12-r10-r18-migrations", "2a833225bc5f2dfc720219d6765b034bd6bd6288", "recovery_forward_migrations_0023_0026_20261016", "manifest.json", "de0684e2", "artifacts", "source", None, True),
    ("C-review", "recovery-forward-migrations-review1", "2a833225bc5f2dfc720219d6765b034bd6bd6288", "recovery_forward_migrations_review1_20261016", "manifest.json", "507c157", "artifacts", None, None, False),
    ("C-append", "recovery-forward-migrations-review1", "2a833225bc5f2dfc720219d6765b034bd6bd6288", "recovery_forward_migrations_review1_20261016", "cr_appendix/manifest.json", "4b2d06de", "artifacts", None, "reports/reviews/recovery/G-D-recovery-forward-migrations-review-1-cr-appendix.md", False),
    ("D-author", "r18-api-key-expiry-fix2", "34af66115a80c3cbedcb10a6d5a349a8af4d4822", "recovery_r18_api_key_expiry_fix2_20261016", "artifact_manifest.json", "54594f79", "files", None, None, True),
    ("D-review", "r18-api-key-review1-fix2", "34af66115a80c3cbedcb10a6d5a349a8af4d4822", "recovery_r18_api_key_review1_fix2_20261016", "review_manifest.json", "5edbd233d3612d1ea39871a1c021cd54583eb00b6a085b91cae149dd3217bcc3", "files", None, None, False),
    ("E-author", "r18-mcp-output-budget-fix1", "260942efc77168683b2b978747a19c3c9fedce3e", "recovery_r18_mcp_output_budget_fix1_20261016", "artifact_manifest.json", "3186563", "files", None, None, True),
    ("E-review", "r18-mcp-output-budget-review1-fix1", "260942efc77168683b2b978747a19c3c9fedce3e", "recovery_r18_mcp_output_budget_review1_fix1_20261016", "artifact_manifest.json", "b65fdba", "files", None, None, False),
    ("F-author", "r17-integrated-sbom-browser", "f1f2bc49ccd33be7e0b150482b253399a4ad7c64", "recovery_r17_integrated_sbom_browser_20261016", "artifact_manifest.json", "a49fb4cf", "members", None, "reports/tasks/R17-integrated-sbom-browser.md", True),
    ("F-review", "r17-real-sbom-browser-review1", "92c809004c65a62e517fd2ef598f2e32a32da0b0", "recovery_r17_integrated_sbom_browser_review1_20261016", "artifact_manifest.json", "40359454", "members", None, "reports/reviews/recovery/G-E-R17-integrated-sbom-browser-review-1.md", True),
    ("F-append", "r17-main-sbom-fresh-proof", "be60a4a6875fc25381274205f58000a02006eee0", "recovery_r17_main_sbom_fresh_proof_20261016", "artifact_manifest.json", "5b7acde9", "members", None, "reports/reviews/recovery/G-E-R17-integrated-sbom-browser-review-1-fresh-main.md", True),
]


def now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="microseconds")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def identity(raw: bytes) -> dict:
    return {"bytes": len(raw), "raw_sha256": sha(raw), "crlf_sequences": raw.count(b"\r\n"), "LF_view_sha256": sha(raw.replace(b"\r\n", b"\n"))}


def git(root: pathlib.Path, *arguments: str) -> bytes:
    return subprocess.run(["git", "-C", str(root), *arguments], capture_output=True, check=True).stdout


def blobs(root: pathlib.Path, commit: str, paths: list[str]) -> dict:
    output = subprocess.run(["git", "-C", str(root), "cat-file", "--batch"], input="".join(f"{commit}:{path}\n" for path in paths).encode(), capture_output=True, check=True).stdout
    result = {}
    position = 0
    for path in paths:
        end = output.index(b"\n", position)
        header = output[position:end].decode()
        position = end + 1
        if header.endswith(" missing"):
            result[path] = None
            continue
        oid, kind, length = header.split()
        if kind != "blob":
            raise ValueError(f"Expected frozen blob: {path}")
        raw = output[position:position + int(length)]
        result[path] = {"oid": oid, "raw": raw}
        position += int(length) + 1
    return result


def write_once(path: pathlib.Path, raw: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as file:
            file.write(raw)
    except FileExistsError:
        if path.read_bytes() != raw:
            raise FileExistsError(f"Canonical conflict retained: {path}")
        return "identical_skip"
    return "copied_new"


def relative_path(value: str, root: pathlib.Path, run: str) -> str:
    cleaned = value.replace("\\", "/")
    if ":" in cleaned:
        return pathlib.Path(cleaned).relative_to(root).as_posix()
    if cleaned.startswith(("reports/", "backend/", "frontend/", "sdk/", "contracts/", "docs/")):
        return cleaned
    return run + "/" + cleaned


def prepare(config: tuple) -> dict:
    label, directory, commit, run_name, manifest_name, prefix, key, source_key, report, committed = config
    root = pathlib.Path("D:/wt") / directory
    run = "reports/runs/" + run_name
    observed = git(root, "rev-parse", "HEAD").decode().strip()
    if observed != commit:
        raise ValueError(f"Source HEAD drift: {label}")
    manifest_path = run + "/" + manifest_name
    manifest_raw = (root / manifest_path).read_bytes()
    if not sha(manifest_raw).startswith(prefix):
        raise ValueError(f"Expected manifest prefix mismatch: {label}")
    manifest = json.loads(manifest_raw)
    members = manifest[key] if key else manifest
    source_members = manifest[source_key] if source_key else []
    expected = {}
    for member in members + source_members:
        path = relative_path(member["path"], root, run)
        digest = next(member[field] for field in ["raw_sha256", "sha256_raw", "sha256"] if field in member)
        if path in expected:
            raise ValueError(f"Duplicate original member: {path}")
        expected[path] = {"expected_raw_sha256": digest, "original_member": True, "declaration": member}
    extras = [manifest_path]
    if report:
        extras.append(report)
    if label.startswith("F-"):
        archive = run + "/evidence_exact_raw.tar.gz"
        if sha((root / archive).read_bytes()) != manifest["archive_sha256"]:
            raise ValueError(f"Original TAR SHA mismatch: {label}")
        extras.append(archive)
        if label == "F-author":
            extras += git(root, "ls-tree", "-r", "--name-only", commit, "--", run).decode().splitlines()
    for path in extras:
        if path not in expected:
            expected[path] = {"expected_raw_sha256": sha((root / path).read_bytes()), "original_member": False, "declaration": {}}
    frozen = blobs(root, commit, list(expected))
    raw_map = {}
    rows = []
    errors = []
    for path, specification in expected.items():
        if ".." in pathlib.PurePosixPath(path).parts or pathlib.PurePosixPath(path).is_absolute():
            raise ValueError(f"Unsafe path: {path}")
        raw = (root / path).read_bytes()
        if sha(raw) != specification["expected_raw_sha256"]:
            errors.append({"kind": "source_raw_manifest_mismatch", "path": path, "expected": specification["expected_raw_sha256"], "observed": sha(raw)})
        row = {"path": path, **specification, "source_before": identity(raw)}
        allowed = path.startswith(run + "/") or path.startswith(("reports/tasks/", "reports/reviews/recovery/"))
        row["canonical_allowed"] = allowed
        blob = frozen[path]
        if blob:
            row["actual_frozen_Git_blob"] = {"oid": blob["oid"], **identity(blob["raw"]), "equals_original_raw": blob["raw"] == raw, "equals_original_LF_view": blob["raw"] == raw.replace(b"\r\n", b"\n")}
            if not (blob["raw"] == raw or blob["raw"] == raw.replace(b"\r\n", b"\n")):
                errors.append({"kind": "source_Git_neither_raw_nor_LF", "path": path})
            declared_git = next((specification["declaration"][field] for field in ["git_blob_sha256", "sha256_git_lf", "code_git_blob_sha256"] if field in specification["declaration"]), None)
            if declared_git is not None and sha(blob["raw"]) != declared_git:
                errors.append({"kind": "declared_Git_SHA_mismatch", "path": path})
        elif committed:
            errors.append({"kind": "frozen_commit_missing", "path": path})
        else:
            row["post_material_or_uncommitted_review_bytes"] = True
        if allowed:
            target = ROOT / path
            row["canonical_before"] = identity(target.read_bytes()) if target.exists() else None
            if row["canonical_before"] and row["canonical_before"]["raw_sha256"] != sha(raw):
                errors.append({"kind": "canonical_conflict_no_overwrite", "path": path, "expected": sha(raw), "observed": row["canonical_before"]["raw_sha256"]})
        else:
            row["policy_excluded_readonly"] = True
        rows.append(row)
        raw_map[path] = raw
    archives = []
    for path, raw in raw_map.items():
        if path.endswith(".tar.gz"):
            archive_manifest = None
            if label.startswith("F-"):
                paired_name = "artifact_manifest_v2_units_only.json" if path.endswith("/evidence_v2_units_only.tar.gz") else "artifact_manifest.json"
                paired_path = run + "/" + paired_name
                archive_manifest = json.loads(raw_map[paired_path])
                if sha(raw) != archive_manifest["archive_sha256"]:
                    raise ValueError(f"Paired historical archive SHA mismatch: {path}")
                declared_archive_members = {member["path"]: member for member in archive_manifest["members"]}
            with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
                entries = archive.getmembers()
                matched = 0
                unmatched = []
                if archive_manifest is not None and set(entry.name for entry in entries) != set(declared_archive_members):
                    raise ValueError(f"Paired historical archive member scope mismatch: {path}")
                for entry in entries:
                    if not entry.isfile():
                        raise ValueError(f"Nonfile sealed TAR member: {path}")
                    member_path = entry.name if entry.name.startswith(("reports/", "backend/")) else run + "/" + entry.name
                    expanded = archive.extractfile(entry).read()
                    if archive_manifest is not None:
                        declaration = declared_archive_members[entry.name]
                        if sha(expanded) != declaration["raw_sha256"] or len(expanded) != declaration["size"]:
                            errors.append({"kind": "paired_archive_original_manifest_mismatch", "archive": path, "path": entry.name})
                        matched += 1
                    elif member_path in raw_map:
                        if expanded != raw_map[member_path]:
                            errors.append({"kind": "archive_member_current_raw_difference", "path": member_path, "archive_original": sha(expanded), "current_raw": sha(raw_map[member_path])})
                        matched += 1
                    else:
                        unmatched.append({"path": entry.name, **identity(expanded)})
                archives.append({"path": path, **identity(raw), "members": len(entries), "mapped_members": matched, "paired_original_manifest": paired_path if archive_manifest is not None else None, "unmapped_members_sealed_only": unmatched, "format_modified": False})
        elif path.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                if archive.testzip() is not None:
                    raise ValueError(f"Invalid sealed ZIP CRC: {path}")
                archives.append({"path": path, **identity(raw), "members": len(archive.infolist()), "CRC_verified": True, "sealed_original_only_no_recursive_input_lookup": True, "format_modified": False})
    return {"id": label, "source_workspace": str(root), "fixed_commit": commit, "fixed_tree": git(root, "rev-parse", commit + "^{tree}").decode().strip(), "manifest": {"path": manifest_path, **identity(manifest_raw), "provided_digest_was_prefix": len(prefix) < 64, "full_digest_observed": sha(manifest_raw), "artifact_members": len(members), "source_members": len(source_members)}, "files": rows, "raw_archives": archives, "errors": errors, "raw_map": raw_map, "artifact_sensitive_status": "Original explicit proof scope retained; archiver did not load runtime secrets or certify universal zero."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("group", choices=list("ABCDEF"))
    parser.add_argument("--attempt", choices=["primary", "recheck"], default="primary")
    arguments = parser.parse_args()
    group = arguments.group
    suffix = "_recheck" if arguments.attempt == "recheck" else ""
    started = now()
    protection = {path: identity((ROOT / path).read_bytes()) for path in [".gitattributes", "frontend/tsconfig.tsbuildinfo"]}
    packages = [prepare(config) for config in CONFIG if config[0].startswith(group + "-")]
    errors = [error for package in packages for error in package["errors"]]
    if not errors:
        for package in packages:
            for row in package["files"]:
                path = row["path"]
                if row["canonical_allowed"]:
                    row["action"] = write_once(ROOT / path, package["raw_map"][path])
                    row["canonical_after"] = identity((ROOT / path).read_bytes())
                else:
                    row["action"] = "excluded_readonly"
                row["source_after"] = identity((pathlib.Path(package["source_workspace"]) / path).read_bytes())
                if row["source_after"] != row["source_before"]:
                    raise ValueError(f"Original source drift: {path}")
    rows = [(package["id"], row) for package in packages for row in package["files"] if row["canonical_allowed"]]
    for package in packages:
        del package["raw_map"]
    filelist = "package\tpath\tbytes\tsha256\taction\n" + "".join(f"{label}\t{row['path']}\t{row['source_before']['bytes']}\t{row['source_before']['raw_sha256']}\t{row.get('action', 'blocked_no_copy')}\n" for label, row in rows)
    filelist_path = RUN / f"group_{group}{suffix}_filelist.tsv"
    write_once(filelist_path, filelist.encode())
    summary = {"canonical_files": len(rows), "copied_new": sum(row.get("action") == "copied_new" for _, row in rows), "identical_skip": sum(row.get("action") == "identical_skip" for _, row in rows), "raw_bytes": sum(row["source_before"]["bytes"] for _, row in rows), "overwrites": 0, "errors": len(errors), "excluded_readonly_members": sum(not row["canonical_allowed"] for package in packages for row in package["files"])}
    receipt = {"batch": 16, "group": group, "status": "blocked" if errors else "awaiting_review", "role": "frozen bytes archive only", "started_at": started, "ended_at": now(), "summary": summary, "packages": packages, "filelist": {"path": str(filelist_path), **identity(filelist.encode())}, "protection_before": protection, "protection_after": {path: identity((ROOT / path).read_bytes()) for path in protection}, "business_tests": "not_run", "Git_index_commit_push_progress_rootattrs_changes": False, "historical_inventory_rechecked": False, "runtime_secrets_loaded": 0, "network_or_paid_API": 0, "source_seal_or_review_scripts_executed": 0}
    receipt_path = RUN / f"group_{group}{suffix}_receipt.json"
    raw = (json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode()
    write_once(receipt_path, raw)
    write_once(receipt_path.with_suffix(".sha256"), (sha(raw) + "\n").encode())
    print(json.dumps({"receipt": str(receipt_path), "receipt_sha256": sha(raw), "summary": summary, "errors": errors, "reports": [row["path"] for _, row in rows if row["path"].startswith(("reports/tasks/", "reports/reviews/"))]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
