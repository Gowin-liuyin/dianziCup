"""Verify fixed retained CAS bytes with current parser and downloaded official legacy schema."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from jsonschema import Draft7Validator

from ai_intel.enrichment.taxonomy_inputs import CatalogueProvenance, parse_atlas_catalogue, parse_cwe_catalogue

RUN = Path(__file__).resolve().parent
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
first = json.loads((RUN / "taxonomy_fetch_manifest.json").read_text())
second = json.loads((RUN / "atlas_new_org_fetch_manifest.json").read_text())
cwe = next(item for item in first if item["label"] == "cwe_4_19")
atlas = next(item for item in second if item["url"].endswith("dist/ATLAS.yaml"))
schema_receipt = next(item for item in second if item["url"].endswith("atlas_output_schema.json"))
observation = {"started_at": started, "network_requests": 0, "model_calls": 0,
               "default_app_integrated": False}
for kind, receipt, version, parser in [
    ("cwe", cwe, "4.19", parse_cwe_catalogue),
    ("atlas", atlas, json.loads((RUN / "taxonomy_parse_observation.json").read_text())["atlas_commit"], parse_atlas_catalogue),
]:
    raw = Path(receipt["cas_path"]).read_bytes()
    assert len(raw) == receipt["bytes"]
    assert hashlib.sha256(raw).hexdigest() == receipt["sha256"]
    catalogue = parser(raw, CatalogueProvenance(
        kind=kind, canonical_uri=receipt["url"], snapshot_version=version, content_sha256=receipt["sha256"],
    ))
    observation[kind] = {"source_hash": receipt["sha256"], "source_bytes": len(raw),
                         "supported_ids": len(catalogue.supported_ids),
                         "content_version": catalogue.content_version,
                         "extracted_content_sha256": catalogue.extracted_content_sha256,
                         "format_version": catalogue.format_version}
    if kind == "atlas":
        schema_raw = Path(schema_receipt["cas_path"]).read_bytes()
        assert hashlib.sha256(schema_raw).hexdigest() == schema_receipt["sha256"]
        schema = json.loads(schema_raw)
        assert all(ref.startswith("#/") for ref in __import__("re").findall(r'"\$ref"\s*:\s*"([^"]+)"', schema_raw.decode()))
        errors = list(Draft7Validator(schema).iter_errors(yaml.safe_load(raw)))
        observation[kind]["official_schema_errors"] = len(errors)
        observation[kind]["official_schema_examples"] = [
            {"path": list(error.absolute_path), "validator": error.validator,
             "message": error.message[:240]} for error in errors[:10]
        ]
        quotes = [entry for entry in catalogue.entries if entry.identifier_quote is not None]
        assert len(quotes) == len(catalogue.entries)
        assert all(raw.decode()[entry.start_offset:entry.end_offset] == entry.identifier_quote for entry in quotes)
        observation[kind]["verified_identifier_quotes"] = len(quotes)
observation["completed_at"] = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
(RUN / "catalogue_replay_fix2_observation.json").write_text(json.dumps(observation, indent=2), encoding="utf-8")
print(json.dumps(observation))
raise SystemExit(1 if observation["atlas"]["official_schema_errors"] else 0)
