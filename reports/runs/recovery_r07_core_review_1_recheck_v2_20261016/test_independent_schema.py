"""Check original malformed bytes and unnormalized omission/null cases independently."""

import copy
import hashlib
import json
import subprocess
import sys
import types
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from ai_intel.api.knowledge_contracts import EnrichmentProjection
from ai_intel.domain.records import ClaimRecord
from ai_intel.domain.schema_export import render_schema_bundle
from ai_intel.enrichment.persistence import DimensionSubmission

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
ORIGINAL = Path("D:/wt/r07-core-review-1/reports/runs/recovery_r07_core_review_1_20261015/independent_values.json")
ORIGINAL_BYTES = ORIGINAL.read_bytes()
ORIGINAL_CASES = {case["label"]: case["input"] for case in json.loads(ORIGINAL_BYTES)["cases"]}
VALIDATOR = Draft202012Validator(ClaimRecord.model_json_schema(), format_checker=FormatChecker())
OBSERVATIONS = []


def observe(label, payload, expected):
    encoded = json.dumps(payload, ensure_ascii=False)
    try:
        ClaimRecord.model_validate_json(encoded)
        runtime_valid = True
    except ValidationError:
        runtime_valid = False
    schema_valid = VALIDATOR.is_valid(json.loads(encoded))
    OBSERVATIONS.append({"label": label, "input": payload, "expected": expected, "runtime_valid": runtime_valid, "schema_valid": schema_valid})
    (RUN / "independent_schema_observations.json").write_text(json.dumps({"recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "original_source": str(ORIGINAL), "original_sha256": hashlib.sha256(ORIGINAL_BYTES).hexdigest(), "cases": OBSERVATIONS}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    assert runtime_valid is expected
    assert schema_valid is expected


@pytest.mark.parametrize("label", ["both_upper_boundaries", "empty_boundary", "unpaired_literature_target"])
def test_original_trigger_is_rejected_at_runtime_and_exported_boundary(label):
    observe("original_" + label, copy.deepcopy(ORIGINAL_CASES[label]), False)


@pytest.mark.parametrize("interval,expected", [
    ({}, False),
    ({"introduced": None, "fixed": None, "last_affected": None}, False),
    ({"branch": "main", "introduced": None, "fixed": None, "last_affected": None}, False),
    ({"fixed": "1.2", "last_affected": "1.1"}, False),
    ({"introduced": "1.0", "fixed": ""}, False),
    ({"introduced": "1.0"}, True),
    ({"fixed": "1.2"}, True),
    ({"last_affected": "1.1"}, True),
    ({"introduced": "0", "fixed": None, "last_affected": None}, True),
    ({"introduced": "1.0", "fixed": "1.2", "last_affected": None, "branch": None}, True),
    ({"introduced": "1.0", "last_affected": "1.1", "fixed": None, "branch": "main"}, True),
])
def test_raw_version_interval_omission_null_and_nonempty_boundaries(interval, expected):
    payload = copy.deepcopy(ORIGINAL_CASES["valid_version"])
    payload["object_value"]["intervals"] = [interval]
    observe("interval_" + str(len(OBSERVATIONS)), payload, expected)


UUID_A = "12345678-1234-5678-1234-567812345678"
UUID_B = "87654321-4321-8765-4321-876543218765"


@pytest.mark.parametrize("identities,expected", [
    ({}, True),
    ({"target_document_id": None}, True),
    ({"target_revision_id": None}, True),
    ({"target_document_id": None, "target_revision_id": None}, True),
    ({"target_document_id": UUID_A}, False),
    ({"target_revision_id": UUID_B}, False),
    ({"target_document_id": UUID_A, "target_revision_id": None}, False),
    ({"target_document_id": None, "target_revision_id": UUID_B}, False),
    ({"target_document_id": UUID_A, "target_revision_id": UUID_B}, True),
    ({"target_document_id": "malformed", "target_revision_id": UUID_B}, False),
])
def test_raw_literature_identity_pair_has_matching_schema_and_runtime(identities, expected):
    payload = copy.deepcopy(ORIGINAL_CASES["unpaired_literature_target"])
    payload["object_value"].pop("target_document_id", None)
    payload["object_value"].pop("target_revision_id", None)
    payload["object_value"].update(identities)
    observe("identities_" + str(len(OBSERVATIONS)), payload, expected)


def git_blob(revision, path):
    return subprocess.check_output(["git", "show", revision + ":" + path], cwd=ROOT)


@pytest.mark.parametrize("path,name,current", [
    ("backend/src/ai_intel/api/knowledge_contracts.py", "EnrichmentProjection", EnrichmentProjection),
    ("backend/src/ai_intel/enrichment/persistence.py", "DimensionSubmission", DimensionSubmission),
])
def test_old_dto_schema_is_equal_to_pre_r07_git_source(path, name, current):
    before_source = git_blob("1a52e17ffe327fb8a0c1d4f97372948a699910e3", path)
    (RUN / ("baseline_" + name + ".py")).write_bytes(before_source)
    module = types.ModuleType("independent_baseline_" + name)
    module.__file__ = str(RUN / ("baseline_" + name + ".py"))
    sys.modules[module.__name__] = module
    exec(compile(before_source, module.__file__, "exec"), module.__dict__)
    before_schema = getattr(module, name).model_json_schema()
    after_schema = current.model_json_schema()
    before_bytes = (json.dumps(before_schema, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
    after_bytes = (json.dumps(after_schema, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
    (RUN / ("dto_before_" + name + ".json")).write_bytes(before_bytes)
    (RUN / ("dto_after_" + name + ".json")).write_bytes(after_bytes)
    assert before_schema == after_schema
    assert before_bytes == after_bytes


def test_schema_bundle_exact_export_and_only_expected_two_constraint_changes():
    rendered = render_schema_bundle().encode()
    frozen = git_blob("cb34097898b412390ee7e119d0d5c2c90d090673", "contracts/schemas/schema_bundle.json")
    assert rendered == frozen
    previous = json.loads(git_blob("74d8e9ba8b49360ca90ade390f7b6c00cd40b815", "contracts/schemas/schema_bundle.json"))
    current = json.loads(rendered)
    assert "allOf" in current["schemas"]["ClaimRecord"]["$defs"]["VersionInterval"]
    assert "oneOf" in current["schemas"]["ClaimRecord"]["$defs"]["LiteratureReferenceValue"]
    current["schemas"]["ClaimRecord"]["$defs"]["VersionInterval"].pop("allOf")
    current["schemas"]["ClaimRecord"]["$defs"]["LiteratureReferenceValue"].pop("oneOf")
    assert current == previous
    (RUN / "bundle_compatibility.json").write_text(json.dumps({"rendered_sha256": hashlib.sha256(rendered).hexdigest(), "frozen_git_blob_sha256": hashlib.sha256(frozen).hexdigest(), "only_changed_schema_nodes": ["ClaimRecord.$defs.VersionInterval.allOf", "ClaimRecord.$defs.LiteratureReferenceValue.oneOf"], "all_other_schema_content_equal": True}, indent=2) + "\n", encoding="utf-8", newline="\n")
