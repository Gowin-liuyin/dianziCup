"""Record actual frozen normalizer outputs for the two review reproductions."""

import json
from pathlib import Path

from ai_intel.ingestion.catalog_pages import normalize_catalog_page

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
body = (ROOT / "fixtures/recorded/cac_generative_ai_20261015_public.html").read_bytes()
changed = body.replace("本办法自2023年8月15日起施行。".encode(), b"")
(RUN / "cac_missing_last_body.input.html").write_bytes(changed)
policy = normalize_catalog_page("cac_generative_ai", changed, {}).documents[0]
record = json.loads((ROOT / "reports/runs/recovery_r06_repository_community_20261015/osv_ollama_real.body").read_bytes())
times = []
for timestamp in ("2026-10-15T01:02:03-00:00", "2026-10-15T01:02:03+00:99", "2026-10-15T01:02:03.1234567Z"):
    record["published"] = timestamp
    raw = json.dumps({"vulns": [record]}, indent=2).encode()
    filename = f"osv_invalid_timestamp_{len(times) + 1}.input.json"
    (RUN / filename).write_bytes(raw)
    document = normalize_catalog_page("osv_ollama", raw, {}).documents[0]
    times.append({"input_file": filename, "published_at_raw": timestamp,
                  "actual_published_utc": document.published_at.isoformat()})
print(json.dumps({"cac": {"input_file": "cac_missing_last_body.input.html",
    "actual_parse_status": policy.parsed.status,
    "actual_content_coverage": policy.metadata["content_coverage"],
    "has_last_heading": "第二十四条" in policy.parsed.normalized_text,
    "has_last_body": "本办法自2023年8月15日起施行。" in policy.parsed.normalized_text,
    "has_preface_effective_sentence": "现予公布，自2023年8月15日起施行。" in policy.parsed.normalized_text},
    "osv": times}, ensure_ascii=False, indent=2))
