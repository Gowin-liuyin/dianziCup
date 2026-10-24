"""Assembles validated candidate bundles into a versioned dev-set manifest; never admits labels or holdout."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.annotation.prepare import (
    PreparationError,
    candidate_payload,
    digest,
    read_document,
    scan_leaks,
    validate_candidates,
    write_new,
)

DEV_SET_SCHEMA_PATH = Path("benchmarks/schemas/dev_set_manifest_v1.json")
CANDIDATE_SCHEMA_PATH = Path("benchmarks/schemas/candidate_case_v1.json")
AWAITING_LABEL_STATUS = "awaiting_human_label"
DATA_KINDS = ("real", "synthetic", "redacted", "replay")
SPLITS = ("dev", "demo")
SCALE_STATEMENT = (
    "候选/种子规模声明：本 dev-set 为 awaiting_human_label 候选装配物，"
    "仅用于标注规则验证与人工准备，不是金标（human_gold_count=0），"
    "不参与任何正式指标计算。"
)


def beijing_now() -> str:
    """Second-precision Beijing timestamp matching the candidate_case_v1 time format."""
    return datetime.now(timezone(timedelta(hours=8))).strftime(
        "%Y-%m-%dT%H:%M:%S+08:00"
    )


def refuse_disallowed_cases(document: dict[str, object]) -> None:
    """Rejects holdout splits and any non-awaiting label status before deeper validation."""
    cases = document.get("cases")
    if not isinstance(cases, list):
        return
    for case in cases:
        if not isinstance(case, dict):
            continue
        if case.get("split") == "holdout":
            raise PreparationError("HOLDOUT_SPLIT_REFUSED")
        if "label_status" in case and case["label_status"] != AWAITING_LABEL_STATUS:
            raise PreparationError("LABEL_STATUS_NOT_AWAITING")


def validate_dev_set_manifest(document: dict[str, object]) -> None:
    """Validates against dev_set_manifest_v1 with candidate_case_v1 definitions merged in."""
    dev_set_schema = read_document(ROOT / DEV_SET_SCHEMA_PATH)
    candidate_schema = read_document(ROOT / CANDIDATE_SCHEMA_PATH)
    merged = {
        "$ref": "#/$defs/dev_set_manifest",
        "$defs": {**candidate_schema["$defs"], **dev_set_schema["$defs"]},
    }
    validator = Draft202012Validator(merged, format_checker=FormatChecker())
    if next(iter(validator.iter_errors(document)), None) is not None:
        raise PreparationError("DEV_SET_SCHEMA_INVALID")


def bundle_reference(path: Path) -> str:
    """Records repo-relative POSIX provenance for in-repo bundles, absolute paths otherwise."""
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return str(resolved)


def data_kind_counts(cases: list[dict[str, object]]) -> dict[str, int]:
    return {kind: sum(case["data_kind"] == kind for case in cases) for kind in DATA_KINDS}


def source_bundle_record(
    path: Path, document: dict[str, object], cases: list[dict[str, object]]
) -> dict[str, object]:
    return {
        "path": bundle_reference(path),
        "candidate_sha256": digest(candidate_payload(document)),
        "case_count": len(cases),
        "data_kind_counts": data_kind_counts(cases),
    }


def gold_block() -> dict[str, object]:
    return {
        "human_gold_count": 0,
        "gold_status": "none_no_human_labels",
        "formal_evaluation": {
            "status": "not_run",
            "numerator": None,
            "denominator": None,
        },
    }


def assemble_dev_set(
    bundles: list[tuple[Path, dict[str, object]]], dev_set_id: str | None
) -> dict[str, object]:
    """Merges preloaded bundles, rechecks identity domains across bundles, and returns the manifest."""
    prepared_at = beijing_now()
    source_bundles: list[dict[str, object]] = []
    merged_cases: list[dict[str, object]] = []
    for path, document in bundles:
        refuse_disallowed_cases(document)
        cases = validate_candidates(document)
        source_bundles.append(source_bundle_record(path, document, cases))
        merged_cases.extend(cases)
    merged_document = {
        "schema_version": 1,
        "prepared_at": prepared_at,
        "cases": merged_cases,
    }
    validate_candidates(merged_document)
    counts = {
        "by_data_kind": data_kind_counts(merged_cases),
        "by_split": {
            split: sum(case["split"] == split for case in merged_cases)
            for split in SPLITS
        },
    }
    label_status_counts = {AWAITING_LABEL_STATUS: len(merged_cases)}
    dev_set_sha256 = digest(
        {
            "cases": merged_cases,
            "counts": counts,
            "label_status_counts": label_status_counts,
        }
    )
    if dev_set_id is None:
        dev_set_id = f"dev-set-{dev_set_sha256[:16]}"
    summary = {
        "dev_set_id": dev_set_id,
        "assembled_at": prepared_at,
        "source_bundles": source_bundles,
        "counts": counts,
        "label_status_counts": label_status_counts,
        "gold": gold_block(),
        "dev_set_sha256": dev_set_sha256,
        "scale_statement": SCALE_STATEMENT,
    }
    manifest = {
        "schema_version": 1,
        "prepared_at": prepared_at,
        "cases": merged_cases,
        "candidate_sha256": digest(candidate_payload(merged_document)),
        "summary": summary,
    }
    validate_dev_set_manifest(manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dev-set-id")
    parser.add_argument("--scan-root", type=Path, action="append", default=[])
    args = parser.parse_args(argv)
    try:
        if not args.bundle:
            raise PreparationError("BUNDLE_REQUIRED")
        bundles = [(path, read_document(path)) for path in args.bundle]
        manifest = assemble_dev_set(bundles, args.dev_set_id)
        if args.scan_root:
            scan_leaks(manifest["cases"], args.scan_root)
        write_new(args.output, manifest)
        summary = manifest["summary"]
        print(
            json.dumps(
                {
                    "dev_set_id": summary["dev_set_id"],
                    "case_count": len(manifest["cases"]),
                    "counts": summary["counts"],
                    "label_status_counts": summary["label_status_counts"],
                    "gold": summary["gold"],
                    "dev_set_sha256": summary["dev_set_sha256"],
                    "output": str(args.output),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except (PreparationError, OSError, ValueError) as error:
        code = (
            str(error) if isinstance(error, PreparationError) else "INPUT_OR_OUTPUT_ERROR"
        )
        print(f"PREPARATION_INVALID: {code}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
