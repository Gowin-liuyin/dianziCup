"""Freeze versioned public envelopes while preserving all legacy definitions."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def object_schema(properties, required=None, **rules):
    return {"type": "object", "properties": properties, "required": list(properties) if required is None else required, "additionalProperties": False, **rules}


def ref(name):
    return {"$ref": "#/$defs/" + name}


def array(items, maximum, **rules):
    return {"type": "array", "items": items, "maxItems": maximum, **rules}


def enumeration(*values):
    return {"enum": list(values)}


started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
legacy_path = ROOT / "contracts/schemas/public_api_v2.json"
legacy_raw = legacy_path.read_bytes()
legacy = json.loads(legacy_raw, object_pairs_hook=strict_object)
definitions = dict(legacy["$defs"])
assert len(definitions) == 14
legacy_digest = hashlib.sha256(json.dumps(legacy, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
identifier = {"type": "string", "format": "uuid"}
nullable_date = {"type": ["string", "null"], "format": "date-time"}
text = {"type": "string", "minLength": 1, "maxLength": 500}
cursor = {"type": ["string", "null"], "minLength": 1, "maxLength": 2048}
data_mode = enumeration("live", "fixture")
severity = enumeration("low", "medium", "high", "critical")
freshness = enumeration("current", "stale", "unknown")
definitions["RiskFinding"] = object_schema({
    "component_index": {"type": "integer", "minimum": 0, "maximum": 199},
    "event_id": identifier, "assessment_id": identifier, "rule_id": identifier,
    "rule_version": {"type": "integer", "minimum": 1},
    "grading_claim_id": identifier, "severity": severity,
    "cvss_score": {"type": "number", "minimum": 0, "maximum": 10},
    "cvss_version": enumeration("2.0", "3.0", "3.1", "4.0"),
    "citations": array(ref("Citation"), 100, minItems=1),
    "freshness": {"const": "current"},
}, allOf=[
    {"if": {"properties": {"severity": {"const": name}}, "required": ["severity"]},
     "then": {"properties": {"cvss_score": bounds}}}
    for name, bounds in (
        ("low", {"exclusiveMinimum": 0, "exclusiveMaximum": 4}),
        ("medium", {"minimum": 4, "exclusiveMaximum": 7}),
        ("high", {"minimum": 7, "exclusiveMaximum": 9}),
        ("critical", {"minimum": 9, "maximum": 10}),
    )
])
definitions["RiskSummary"] = object_schema({
    "policy_version": {"const": "r18-risk-policy-1"},
    "minimum_severity": severity,
    "confirmation": enumeration("confirmed", "none_confirmed", "unknown", "conflict"),
    "coverage": enumeration("complete", "partial", "unknown"),
    "freshness": freshness,
    "evaluated_components": {"type": "integer", "minimum": 0, "maximum": 200},
    "unknown_component_indices": array({"type": "integer", "minimum": 0, "maximum": 199}, 200, uniqueItems=True),
    "findings": array(ref("RiskFinding"), 200),
}, allOf=[{
    "if": {"properties": {"confirmation": {"const": "confirmed"}}, "required": ["confirmation"]},
    "then": {"properties": {"findings": {"minItems": 1}}},
}])
definitions["StackCheckEnvelope"] = object_schema({
    "result": ref("StackCheckResult"), "risk_summary": ref("RiskSummary"),
})
definitions["VulnerabilityPage"] = object_schema({
    "items": array(ref("Vulnerability"), 100), "next_cursor": cursor, "data_mode": data_mode,
})
definitions["VulnerabilityDetailPage"] = object_schema({
    "vulnerability": ref("Vulnerability"), "advisories": array(ref("Advisory"), 100),
    "next_cursor": cursor, "mapping_limits": array(text, 100), "data_mode": data_mode,
})
definitions["SourceDescriptor"] = object_schema({
    "source_id": {"type": "string", "minLength": 1, "maxLength": 200}, "name": text,
    "category": enumeration("structured_vulnerability", "vendor_advisory", "security_community", "code_repository", "technical_blog", "academic_paper", "technical_standard", "policy_regulation"),
    "enabled": {"type": "boolean"},
    "health": enumeration("never_polled", "healthy", "partial", "failed", "blocked", "unknown"),
    "last_attempt_at": nullable_date, "last_success_at": nullable_date,
    "reason_code": {"type": ["string", "null"], "minLength": 1, "maxLength": 100},
    "data_mode": data_mode,
})
definitions["SourcePage"] = object_schema({
    "items": array(ref("SourceDescriptor"), 100), "next_cursor": cursor, "data_mode": data_mode,
})
definitions["TaskDescriptor"] = object_schema({
    "task_id": identifier, "task_type": enumeration("ask", "stack_check"),
    "status": enumeration("queued", "running", "retry_wait", "waiting_approval", "succeeded", "partial", "failed", "cancelled", "blocked"),
    "poll_uri": {"type": "string", "pattern": "^/api/v1/tasks/[0-9a-fA-F-]{36}$"},
    "created_at": {"type": "string", "format": "date-time"},
    "updated_at": {"type": "string", "format": "date-time"},
})
definitions["PublicProblem"] = object_schema({
    "type": {"type": "string", "format": "uri"}, "title": text,
    "status": {"type": "integer", "minimum": 400, "maximum": 599},
    "error": {"type": "string", "minLength": 1, "maxLength": 100}, "trace_id": identifier,
})
definitions["TaskResultEnvelope"] = object_schema({
    "task": ref("TaskDescriptor"),
    "result": {"anyOf": [ref("QAAnswer"), ref("StackCheckEnvelope"), {"type": "null"}]},
    "error": {"anyOf": [ref("PublicProblem"), {"type": "null"}]},
    "completed_steps": array(text, 100, uniqueItems=True),
    "pending_steps": array(text, 100, uniqueItems=True),
    "failed_steps": array(text, 100, uniqueItems=True),
})
schema = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "urn:dianzi:public-api:extensions:v1",
    "title": "Versioned public API envelopes; legacy v2 definitions preserved",
    "schema_version": 1, "base_schema_id": legacy["$id"],
    "base_schema_canonical_sha256": legacy_digest,
    "x-change-records": ["CR-R09", "CR-R18_public_envelopes_and_output_budget"],
    "$defs": definitions,
}
Draft202012Validator.check_schema(schema)
for name, definition in legacy["$defs"].items():
    assert definitions[name] == definition
target = ROOT / "contracts/schemas/public_api_extensions_v1.json"
assert not target.exists(), "do not overwrite an existing public contract"
target.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
assert legacy_path.read_bytes() == legacy_raw
receipt = {
    "started_at": started,
    "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    "baseline": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "legacy_definitions_preserved": 14, "new_definitions": len(definitions) - 14,
    "legacy_raw_sha256": hashlib.sha256(legacy_raw).hexdigest(),
    "legacy_canonical_sha256": legacy_digest,
    "extension_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
    "schema_check": "passed", "format_checker": type(FormatChecker()).__name__,
    "product_api": "not_run", "independent_review": "pending",
}
(RUN / "contract_generation_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(receipt))
