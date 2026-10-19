"""Minimize AVID reference failures without copying original record text or raw URLs."""

import base64
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

from ai_intel.ingestion.sources.avid_records import _reference_identifier, normalize_avid_vulnerability
from ai_intel.ingestion.sources import avid_records
from ai_intel.ingestion.catalog_pages import normalize_avid_blob, select_avid_blob

from replay_originals import RUN, current_time, failure_summary, static_messages


def verdict(call):
    try:
        call()
        return {"verdict": "passed"}
    except Exception as error:
        return {"verdict": "failed", **failure_summary(error, static_messages())}


started_at = current_time()
entry = json.loads((RUN / "official_response_manifest.json").read_text(encoding="utf-8"))[1]
envelope = json.loads(Path(entry["original_path"]).read_bytes())
payload = base64.b64decode(envelope["content"].replace("\n", ""), validate=True)
document = json.loads(payload)
references = document["references"]
results = []
for index, reference in enumerate(references):
    value = reference.get("url")
    result = {"reference_index": index, "url_type": type(value).__name__,
              **verdict(lambda value=value: _reference_identifier(value))}
    if isinstance(value, str):
        parts = urlsplit(value)
        result.update({"url_sha256": hashlib.sha256(value.encode()).hexdigest(),
                       "url_characters": len(value), "url_ascii": value.isascii(),
                       "whitespace_positions": [offset for offset, character in enumerate(value)
                                                if character.isspace()],
                       "control_positions": [offset for offset, character in enumerate(value)
                                             if ord(character) < 32 or ord(character) == 127],
                       "backslash_present": "\\" in value,
                       "scheme": parts.scheme if parts.scheme in {"http", "https"} else "<other>",
                       "hostname_present": bool(parts.hostname),
                       "userinfo_present": parts.username is not None or parts.password is not None,
                       "query_present": bool(parts.query), "fragment_present": bool(parts.fragment)})
        result["strip_ascii_space_only_probe"] = verdict(lambda value=value: _reference_identifier(value.strip(" ")))
    minimized = dict(document, references=[reference])
    result["record_with_this_reference_only"] = verdict(lambda minimized=minimized: normalize_avid_vulnerability(json.dumps(minimized).encode()))
    results.append(result)
without_references = dict(document, references=[])
tree = json.loads(Path(entry["tree_path"]).read_bytes())
image_members = [{"path": item["path"], "git_blob_sha": item["sha"], "size_bytes": item.get("size")}
                 for item in tree["tree"] if item["path"] == "reports/img/R00031.png"]
original_reference_identifier = avid_records._reference_identifier


def bounded_image_context(value):
    if isinstance(value, str) and re.fullmatch(r"\.\./img/R[0-9]{5}\.png", value):
        return None
    return original_reference_identifier(value)


try:
    avid_records._reference_identifier = bounded_image_context
    selection = select_avid_blob(Path(entry["tree_path"]).read_bytes(), entry["cursor"])
    normalized = normalize_avid_blob(selection, Path(entry["original_path"]).read_bytes())
    image_context_probe = {"verdict": "passed", "identifier": normalized.source_record_id,
                           "parsed_status": normalized.parsed.status,
                           "original_payload_preserved": normalized.payload == payload,
                           "referenced_advisory_ids": normalized.metadata["referenced_advisory_ids"],
                           "next_cursor": selection.next_cursor}
finally:
    avid_records._reference_identifier = original_reference_identifier
output = {"source_sha": "1156b2ed6616e3a4297215c2893d2cbe633f5215", "argv": sys.argv,
          "cwd": os.getcwd(), "started_at": started_at, "finished_at": current_time(),
          "decoded_size_bytes": len(payload), "decoded_sha256": hashlib.sha256(payload).hexdigest(),
          "decoded_git_blob_sha1": hashlib.sha1(b"blob " + str(len(payload)).encode() + b"\0" + payload).hexdigest(),
          "data_type": document["data_type"], "data_version": document["data_version"],
          "references_count": len(references), "reference_results": results,
          "necessary_short_reference_field": "../img/R00031.png",
          "pinned_tree_matching_image_metadata": image_members,
          "bounded_image_context_in_memory_probe": image_context_probe,
          "record_without_references": verdict(lambda: normalize_avid_vulnerability(json.dumps(without_references).encode())),
          "network_requests": 0, "database_calls": 0,
          "classification": "diagnostic local replay; removing fields is not a product fix",
          "exit_code": 0}
(RUN / "avid_reference_probes.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
print(json.dumps(output, indent=2))
