"""Adapts T01 synthetic pilot cases into candidate_case_v1 seed bundles; proposal values never become labels."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.annotation.prepare import (
    PreparationError,
    candidate_payload,
    digest,
    object_list,
    object_value,
    read_document,
    string_value,
    validate_candidates,
    write_new,
)

DEFAULT_INPUT = Path("fixtures/synthetic/pilot_cases.json")
MAX_QUOTE_CHARS = 240


def beijing_now() -> str:
    """Second-precision Beijing timestamp matching the candidate_case_v1 time format."""
    return datetime.now(timezone(timedelta(hours=8))).strftime(
        "%Y-%m-%dT%H:%M:%S+08:00"
    )


def synthetic_family_id(case_id: str) -> str:
    """Groups pilot cases sharing a numeric-suffix prefix into one stable event family."""
    head, _, tail = case_id.rpartition("-")
    if head and tail.isdigit():
        return head
    return case_id


def synthetic_evidence(
    pilot_case: dict[str, object], prepared_at: str
) -> dict[str, object]:
    """Quotes a prefix of the canonicalized synthetic input so hash and offsets stay offline-verifiable."""
    case_id = string_value(pilot_case["case_id"])
    canonical = json.dumps(
        pilot_case["input"], ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    quote_text = canonical[:MAX_QUOTE_CHARS]
    quote_sha256 = hashlib.sha256(quote_text.encode()).hexdigest()
    return {
        "span_id": f"SYNPILOT-SPAN-{case_id}",
        "revision_id": f"SYNPILOT-REVISION-{case_id}",
        "block_id": f"SYNPILOT-BLOCK-{case_id}",
        "start_offset": 0,
        "end_offset": len(quote_text),
        "quote_text": quote_text,
        "quote_sha256": quote_sha256,
        "locator_kind": "json_pointer",
        "page_number": None,
        "json_pointer": "/",
        "source_uri": f"urn:synthetic:{case_id}",
        "verified_at": prepared_at,
        "field_meaning": (
            "合成输入 input 对象规范化 JSON 文本的前缀片段（最长240字符）；"
            "仅用于人工定位合成输入内容，不指向真实来源。"
        ),
    }


def synthetic_candidate_case(
    pilot_case: dict[str, object], prepared_at: str
) -> dict[str, object]:
    """Maps one pilot case to a candidate; expected_result/expected_basis values are never copied."""
    case_id = string_value(pilot_case["case_id"])
    scenario = string_value(pilot_case["scenario"])
    family_id = synthetic_family_id(case_id)
    evidence = synthetic_evidence(pilot_case, prepared_at)
    return {
        "case_id": case_id,
        "event_family_id": family_id,
        "family_aliases": [family_id],
        "data_kind": "synthetic",
        "split": "dev",
        "source_refs": [
            {
                "source_kind": "fixture",
                "uri": f"urn:synthetic:{case_id}",
                "document_id": f"SYNPILOT-DOC-{case_id}",
                "revision_id": f"SYNPILOT-REVISION-{case_id}",
                "revision_number": 1,
                "title": scenario,
                "source_published_at": None,
                "source_modified_at": None,
                "observed_at": prepared_at,
            }
        ],
        "source_snapshot_time": prepared_at,
        "input_refs": [
            {
                "kind": "evidence",
                "ref_id": evidence["span_id"],
                "sha256": evidence["quote_sha256"],
                "path": None,
            }
        ],
        "license": {
            "status": "unknown",
            "identifier": None,
            "uri": None,
            "redistribution": "unverified",
        },
        "candidate_origin": "model_assisted",
        "candidate_task": (
            f"合成场景：{scenario}。两位标注人各自核对合成输入与场景描述，"
            "独立记录可确认事实与尚不可确认的缺口；pilot_cases 中同名 case 的 "
            "expected_result/expected_basis 仅为待复核提案，不得据此预填标签。"
        ),
        "evidence": [evidence],
        "limitations": [
            f"溯源：fixtures/synthetic/pilot_cases.json 原 case_id {case_id}，"
            "T01 agent-drafted 合成案例，仅用于开发与标注规则验证。"
        ],
        "label_status": "awaiting_human_label",
    }


def build_seed_document(pilot_cases: list[dict[str, object]]) -> dict[str, object]:
    """Builds and self-validates a candidate bundle; the caller owns exclusive output writing."""
    prepared_at = beijing_now()
    cases: list[dict[str, object]] = []
    seen_case_ids: set[str] = set()
    for pilot_case in pilot_cases:
        for field in ("case_id", "scenario", "data_kind", "input"):
            if field not in pilot_case:
                raise PreparationError("PILOT_CASE_INVALID")
        if pilot_case.get("is_synthetic") is not True:
            raise PreparationError("PILOT_CASE_NOT_SYNTHETIC")
        case_id = string_value(pilot_case["case_id"])
        if case_id in seen_case_ids:
            raise PreparationError("DUPLICATE_CASE")
        seen_case_ids.add(case_id)
        candidate = synthetic_candidate_case(pilot_case, prepared_at)
        candidate["limitations"].extend(
            [
                f"原 pilot_cases data_kind『{string_value(pilot_case['data_kind'])}』"
                "为 T01 旧值域，本候选统一登记为 synthetic。",
                "pilot_cases 的 expected_result/expected_basis 字段为待复核提案，"
                "不是金标；本候选不含任何预期答案字段，模型不充当唯一出题人与裁判。",
                "许可未审（unknown/unverified）；observed_at/verified_at 为构建时刻"
                "北京时间秒级；证据仅为合成输入规范化文本前缀，不指向真实来源。",
            ]
        )
        cases.append(candidate)
    document = {"schema_version": 1, "prepared_at": prepared_at, "cases": cases}
    document["candidate_sha256"] = digest(candidate_payload(document))
    validate_candidates(document)
    return document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        document = read_document(args.input)
        cases = object_list(object_value(document).get("cases"))
        seed = build_seed_document(cases)
        write_new(args.output, seed)
        print(
            json.dumps(
                {
                    "case_count": len(seed["cases"]),
                    "candidate_sha256": seed["candidate_sha256"],
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
