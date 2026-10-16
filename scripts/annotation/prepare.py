"""Local candidate import, annotation checks and safe exports; never freezes gold labels."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


class PreparationError(ValueError):
    """Carries only a fixed error code, so CLI failures do not disclose input contents."""


def object_value(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise PreparationError("OBJECT_REQUIRED")
    return value


def object_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise PreparationError("LIST_REQUIRED")
    return [object_value(item) for item in value]


def string_value(value: object) -> str:
    if not isinstance(value, str):
        raise PreparationError("STRING_REQUIRED")
    return value


def list_value(value: object) -> list[object]:
    if not isinstance(value, list):
        raise PreparationError("LIST_REQUIRED")
    return value


def integer_value(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise PreparationError("INTEGER_REQUIRED")
    return value


def candidate_payload(document: dict[str, object]) -> dict[str, object]:
    return {key: document[key] for key in ("schema_version", "prepared_at", "cases")}


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def read_document(path: Path) -> dict[str, object]:
    from scripts.verify_plan import load_json

    try:
        if path.stat().st_size > 10_000_000:
            raise PreparationError("INPUT_TOO_LARGE")
        return load_json(path)
    except PreparationError:
        raise
    except (OSError, ValueError):
        raise PreparationError("JSON_INPUT_INVALID") from None


def validate_schema(document: dict[str, object], definition: str) -> None:
    schema = read_document(ROOT / "benchmarks/schemas/candidate_case_v1.json")
    validator = Draft202012Validator(
        {"$ref": f"#/$defs/{definition}", "$defs": schema["$defs"]},
        format_checker=FormatChecker(),
    )
    if next(iter(validator.iter_errors(document)), None) is not None:
        raise PreparationError("SCHEMA_INVALID")


def validate_time(value: object) -> None:
    timestamp = string_value(value)
    parsed = datetime.fromisoformat(timestamp)
    if parsed.utcoffset() != timedelta(hours=8) or parsed.microsecond:
        raise PreparationError("BEIJING_SECOND_TIMESTAMP_REQUIRED")


def safe_reference_path(value: object) -> None:
    reference = string_value(value)
    path = PurePosixPath(reference)
    if (
        not reference
        or "\\" in reference
        or ":" in reference
        or path.is_absolute()
        or any(part in ("..", ".") for part in reference.split("/"))
    ):
        raise PreparationError("REFERENCE_PATH_UNSAFE")


def validate_candidates(document: dict[str, object]) -> list[dict[str, object]]:
    """Checks declared lineage and hard source identities; hidden relationships require humans."""
    validate_schema(document, "candidate_bundle")
    validate_time(document["prepared_at"])
    cases = object_list(document["cases"])
    identifiers: set[str] = set()
    split_by_identity: dict[str, str] = {}
    for case in cases:
        case_id = string_value(case["case_id"])
        if case_id in identifiers:
            raise PreparationError("DUPLICATE_CASE")
        identifiers.add(case_id)
        split = string_value(case["split"])
        validate_time(case["source_snapshot_time"])
        identities = [string_value(case["event_family_id"])]
        for alias in list_value(case["family_aliases"]):
            identities.append(string_value(alias))
        for reference in object_list(case["input_refs"]):
            if reference["path"] is not None:
                safe_reference_path(reference["path"])
        for source in object_list(case["source_refs"]):
            validate_time(source["observed_at"])
            uri = string_value(source["uri"])
            parsed = urlsplit(uri)
            if case["data_kind"] == "synthetic":
                if source["source_kind"] != "fixture" or not uri.startswith(
                    "urn:synthetic:"
                ):
                    raise PreparationError("SYNTHETIC_PROVENANCE_REQUIRED")
            elif source["source_kind"] != "public_document" or (
                parsed.scheme != "https"
                or not parsed.netloc
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
            ):
                raise PreparationError("PUBLIC_PROVENANCE_REQUIRED")
            identities.extend([uri, string_value(source["document_id"])])
        for evidence in object_list(case["evidence"]):
            validate_time(evidence["verified_at"])
            quote = string_value(evidence["quote_text"])
            if hashlib.sha256(quote.encode()).hexdigest() != evidence["quote_sha256"]:
                raise PreparationError("QUOTE_HASH_MISMATCH")
            if integer_value(evidence["end_offset"]) - integer_value(
                evidence["start_offset"]
            ) != len(quote):
                raise PreparationError("QUOTE_OFFSET_MISMATCH")
            if not any(
                source["revision_id"] == evidence["revision_id"]
                and source["uri"] == evidence["source_uri"]
                for source in object_list(case["source_refs"])
            ):
                raise PreparationError("EVIDENCE_SOURCE_MISMATCH")
            if evidence["locator_kind"] == "json_pointer" and not (
                isinstance(evidence["json_pointer"], str)
                and evidence["json_pointer"].startswith("/")
            ):
                raise PreparationError("EVIDENCE_LOCATOR_REQUIRED")
            if (
                evidence["locator_kind"] == "pdf_page"
                and evidence["page_number"] is None
            ):
                raise PreparationError("EVIDENCE_LOCATOR_REQUIRED")
        evidence_by_id = {
            evidence["span_id"]: evidence for evidence in object_list(case["evidence"])
        }
        for reference in object_list(case["input_refs"]):
            if reference["kind"] == "evidence" and (
                reference["ref_id"] not in evidence_by_id
                or reference["sha256"]
                != evidence_by_id[reference["ref_id"]]["quote_sha256"]
            ):
                raise PreparationError("INPUT_EVIDENCE_MISMATCH")
        for identity in identities:
            if identity in split_by_identity and split_by_identity[identity] != split:
                raise PreparationError("FAMILY_SPLIT_LEAK")
            split_by_identity[identity] = split
    if "candidate_sha256" in document and document["candidate_sha256"] != digest(
        candidate_payload(document)
    ):
        raise PreparationError("CANDIDATE_HASH_MISMATCH")
    return cases


def inspect_annotations(
    cases: list[dict[str, object]], annotations: dict[str, object] | None
) -> dict[str, int]:
    """Preserves every label revision and reports readiness, without promoting labels to gold."""
    states = {
        "awaiting_human_label": len(cases),
        "awaiting_adjudication": 0,
        "awaiting_identity_verification": 0,
        "ready_for_manual_review": 0,
    }
    if annotations is None:
        return states
    validate_schema(annotations, "annotation_bundle")
    if annotations["candidate_cases_sha256"] != digest(cases):
        raise PreparationError("LABEL_CANDIDATE_VERSION_MISMATCH")
    if annotations["data_mode"] == "fixture" and any(
        case["data_kind"] != "synthetic" for case in cases
    ):
        raise PreparationError("FIXTURE_LABELS_REQUIRE_SYNTHETIC_CASES")
    current_cases = {string_value(case["case_id"]): case for case in cases}
    latest: dict[tuple[str, str], dict[str, object]] = {}
    for record in object_list(annotations["annotators"]):
        case_id = string_value(record["case_id"])
        if case_id not in current_cases:
            raise PreparationError("LABEL_CASE_UNKNOWN")
        validate_time(record["recorded_at"])
        validate_label(object_value(record["label"]), current_cases[case_id])
        key = (case_id, string_value(record["annotator_id"]))
        previous = latest.get(key)
        revision = record["revision"]
        if previous is None:
            if revision != 1 or record["previous_sha256"] is not None:
                raise PreparationError("LABEL_HISTORY_INVALID")
        elif (
            integer_value(revision) != integer_value(previous["revision"]) + 1
            or record["previous_sha256"] != digest(previous)
            or not record["change_reason"]
            or case_id not in list_value(record["affected_case_ids"])
            or not record["retest_refs"]
            or string_value(record["recorded_at"])
            < string_value(previous["recorded_at"])
        ):
            raise PreparationError("LABEL_REVISION_AUDIT_REQUIRED")
        latest[key] = record
    adjudications = object_list(annotations["adjudication"])
    identity_checks = object_list(annotations["identity_checks"])
    for case in cases:
        case_id = string_value(case["case_id"])
        records = [
            record
            for (label_case, _), record in latest.items()
            if label_case == case_id
        ]
        if len(records) > 2:
            raise PreparationError("EXACTLY_TWO_ANNOTATORS_REQUIRED")
        checks = [item for item in identity_checks if item["case_id"] == case_id]
        decisions = [item for item in adjudications if item["case_id"] == case_id]
        if len(checks) > 1 or len(decisions) > 1:
            raise PreparationError("DUPLICATE_REVIEW_RECORD")
        if len(records) < 2:
            if checks or decisions:
                raise PreparationError("REVIEW_REQUIRES_TWO_CURRENT_LABELS")
            continue
        states["awaiting_human_label"] -= 1
        hashes = {digest(record) for record in records}
        disagree = records[0]["label"] != records[1]["label"]
        if decisions:
            decision = decisions[0]
            validate_time(decision["recorded_at"])
            if {
                string_value(item) for item in list_value(decision["label_sha256s"])
            } != hashes or decision["adjudicator_id"] in {
                record["annotator_id"] for record in records
            }:
                raise PreparationError("ADJUDICATION_INVALID_OR_STALE")
            validate_label(object_value(decision["label"]), case)
        if checks:
            check = checks[0]
            validate_time(check["verified_at"])
            if (
                {string_value(item) for item in list_value(check["annotator_ids"])}
                != {record["annotator_id"] for record in records}
                or {string_value(item) for item in list_value(check["label_sha256s"])}
                != hashes
                or check["verified_by"]
                in {record["annotator_id"] for record in records}
            ):
                raise PreparationError("IDENTITY_ATTESTATION_INVALID_OR_STALE")
        if disagree and not decisions:
            states["awaiting_adjudication"] += 1
        elif not checks:
            states["awaiting_identity_verification"] += 1
        else:
            states["ready_for_manual_review"] += 1
    if any(
        item["case_id"] not in current_cases for item in adjudications + identity_checks
    ):
        raise PreparationError("REVIEW_CASE_UNKNOWN")
    return states


def validate_label(label: dict[str, object], case: dict[str, object]) -> None:
    evidence_ids = {evidence["span_id"] for evidence in object_list(case["evidence"])}
    for claim in object_list(label["expected_claims"]):
        if not {
            string_value(item) for item in list_value(claim["evidence_ids"])
        }.issubset(evidence_ids):
            raise PreparationError("LABEL_EVIDENCE_UNKNOWN")


def summarize(
    cases: list[dict[str, object]], annotations: dict[str, object] | None
) -> dict[str, object]:
    return {
        "candidate_count": len(cases),
        "candidate_counts_by_data_kind": {
            kind: sum(case["data_kind"] == kind for case in cases)
            for kind in ("real", "synthetic", "redacted", "replay")
        },
        "annotation_readiness": inspect_annotations(cases, annotations),
        "human_gold_count": 0,
        "formal_evaluation": {
            "status": "not_run",
            "numerator": None,
            "denominator": None,
        },
    }


def protected_roots(extra_roots: list[Path]) -> list[Path]:
    """Read all current registered worktrees; resolve junctions and fail closed without Git."""
    try:
        registry = subprocess.run(
            ["git", "worktree", "list", "--porcelain", "-z"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError, UnicodeError):
        raise PreparationError("REPOSITORY_WORKTREE_REGISTRY_UNAVAILABLE") from None
    worktrees = [
        Path(field.removeprefix("worktree ")).resolve()
        for field in registry.split("\0")
        if field.startswith("worktree ")
    ]
    if not worktrees:
        raise PreparationError("REPOSITORY_WORKTREE_REGISTRY_UNAVAILABLE")
    return [
        ROOT,
        *worktrees,
        *(path.resolve() for path in extra_roots),
    ]


def require_external(path: Path, roots: list[Path]) -> None:
    resolved = path.resolve()
    if any(resolved == root or resolved.is_relative_to(root) for root in roots):
        raise PreparationError("HUMAN_OR_HOLDOUT_PATH_MUST_BE_EXTERNAL")


def require_unlinked_output_parent(path: Path) -> None:
    """Refuses existing symlink/junction ancestors; hostile concurrent renames remain a limit."""
    if any(
        parent.is_symlink() or (os.name == "nt" and parent.is_junction())
        for parent in path.parents
    ):
        raise PreparationError("OUTPUT_PATH_UNSAFE")


def sync_output_directory(directory: Path) -> None:
    """Syncs POSIX directory entries; Windows file fsync does not promise power-loss durability."""
    if os.name == "nt":
        return
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise PreparationError("OUTPUT_PATH_CHANGED")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def remove_owned_pending(path: Path, created_identity: os.stat_result) -> None:
    """Only unlinks the exact regular file this invocation created, never scans other residues."""
    try:
        current_identity = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISREG(current_identity.st_mode) and os.path.samestat(
        created_identity, current_identity
    ):
        path.unlink()


def write_new(path: Path, document: dict[str, object]) -> None:
    """Publishes complete JSON without replacement; interrupted pending files require validation."""
    path = Path(os.path.abspath(path))
    require_unlinked_output_parent(path)
    if path.exists() or path.is_symlink():
        raise PreparationError("OUTPUT_EXISTS")
    path.parent.mkdir(parents=True, exist_ok=True)
    require_unlinked_output_parent(path)
    parent_identity = path.parent.stat()
    pending: Path | None = None
    created_identity: os.stat_result | None = None
    descriptor, pending_name = tempfile.mkstemp(
        prefix=".r19-pending-", suffix=".json", dir=path.parent
    )
    try:
        try:
            pending = Path(pending_name)
            created_identity = os.fstat(descriptor)
            stream = os.fdopen(descriptor, "w", encoding="utf-8", newline="\n")
        except BaseException:
            os.close(descriptor)
            raise
        with stream as output_stream:
            json.dump(
                document, output_stream, ensure_ascii=False, indent=2, allow_nan=False
            )
            output_stream.write("\n")
            output_stream.flush()
            os.fsync(output_stream.fileno())
        require_unlinked_output_parent(path)
        current_identity = pending.lstat()
        if (
            not os.path.samestat(parent_identity, path.parent.stat())
            or not stat.S_ISREG(current_identity.st_mode)
            or not os.path.samestat(created_identity, current_identity)
        ):
            raise PreparationError("OUTPUT_PATH_CHANGED")
        try:
            os.link(pending, path)
        except FileExistsError:
            raise PreparationError("OUTPUT_EXISTS") from None
        sync_output_directory(path.parent)
    finally:
        if pending is not None and created_identity is not None:
            remove_owned_pending(pending, created_identity)
    sync_output_directory(path.parent)


def scan_leaks(
    cases: list[dict[str, object]],
    roots: list[Path],
    annotations: dict[str, object] | None = None,
) -> None:
    """Scans only operator-selected public trees; a hit prints no file content or labels."""
    holdout = [case for case in cases if case["split"] == "holdout"]
    needles: set[str] = set()
    for case in holdout:
        needles.update(
            [string_value(case["case_id"]), string_value(case["event_family_id"])]
        )
        needles.update(
            string_value(alias) for alias in list_value(case["family_aliases"])
        )
        needles.update(
            string_value(source["uri"]) for source in object_list(case["source_refs"])
        )
        needles.update(
            string_value(evidence["quote_text"])
            for evidence in object_list(case["evidence"])
        )
    if annotations is not None:
        holdout_ids = {case["case_id"] for case in holdout}
        records = object_list(annotations["annotators"]) + object_list(
            annotations["adjudication"]
        )
        for record in records:
            if record["case_id"] in holdout_ids:
                label = object_value(record["label"])
                needles.update(
                    string_value(claim["claim"])
                    for claim in object_list(label["expected_claims"])
                )
    for root in roots:
        if not root.is_dir() or root.is_symlink():
            raise PreparationError("SCAN_ROOT_MISSING")
        for path in root.rglob("*"):
            if path.is_symlink():
                raise PreparationError("SCAN_SYMLINK_REFUSED")
            if path.is_file():
                if path.stat().st_size > 10_000_000:
                    raise PreparationError("SCAN_FILE_TOO_LARGE")
                content = path.read_bytes()
                if any(needle.encode() in content for needle in needles):
                    raise PreparationError("HOLDOUT_LEAK_FOUND")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("validate", "import", "export", "scan"))
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--labels", type=Path)
    parser.add_argument(
        "--purpose",
        choices=("annotation", "prompt", "index", "image", "fixture"),
        default="annotation",
    )
    parser.add_argument("--product-root", type=Path, action="append", default=[])
    parser.add_argument("--scan-root", type=Path, action="append", default=[])
    args = parser.parse_args(argv)
    try:
        roots = protected_roots(args.product_root)
        document = read_document(args.input)
        cases = validate_candidates(document)
        has_holdout = any(case["split"] == "holdout" for case in cases)
        if has_holdout or "annotations" in document:
            require_external(args.input, roots)
        if args.labels is not None:
            require_external(args.labels, roots)
        if args.labels and "annotations" in document:
            raise PreparationError("DUPLICATE_ANNOTATION_INPUT")
        labels = (
            read_document(args.labels)
            if args.labels
            else (
                object_value(document["annotations"])
                if "annotations" in document
                else None
            )
        )
        if "annotations" in document and document.get("annotation_sha256") != digest(
            labels
        ):
            raise PreparationError("ANNOTATION_HASH_MISMATCH")
        summary = summarize(cases, labels)
        if args.action == "scan":
            if not args.scan_root:
                raise PreparationError("SCAN_ROOT_REQUIRED")
            scan_leaks(cases, args.scan_root, labels)
        if args.action in ("import", "export"):
            if args.output is None:
                raise PreparationError("OUTPUT_REQUIRED")
            if labels is not None:
                require_external(args.output, roots)
                if args.action != "export" or args.purpose != "annotation":
                    raise PreparationError("LABEL_EXPORT_REFUSED")
            if has_holdout:
                require_external(args.output, roots)
                if args.action == "export" and args.purpose != "annotation":
                    raise PreparationError("HOLDOUT_EXPORT_REFUSED")
            output = {
                **candidate_payload(document),
                "candidate_sha256": digest(candidate_payload(document)),
                "summary": summary,
            }
            if labels is not None:
                output["annotations"] = labels
                output["annotation_sha256"] = digest(labels)
            write_new(args.output, output)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0
    except (
        PreparationError,
        OSError,
        ValueError,
        subprocess.CalledProcessError,
    ) as error:
        code = (
            str(error)
            if isinstance(error, PreparationError)
            else "INPUT_OR_OUTPUT_ERROR"
        )
        print(f"PREPARATION_INVALID: {code}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
