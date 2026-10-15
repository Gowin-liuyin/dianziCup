"""Two additionally authorized new-org requests; first four observations remain immutable."""

import hashlib
import json
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ai_intel.enrichment.taxonomy_inputs import CatalogueProvenance, parse_atlas_catalogue
from ai_intel.infrastructure.dns_resolver import CloudflareDohResolver
from ai_intel.infrastructure.network import NetworkGateway, NetworkPolicy, RequestDeadline

RUN = Path(__file__).resolve().parent
CAS = Path("D:/dianzi-private/r07-taxonomy-cas")
COMMIT = json.loads((RUN / "taxonomy_parse_observation.json").read_text())["atlas_commit"]
deadline = RequestDeadline(time.monotonic() + 45)
receipts = []
observation = {"commit": COMMIT, "model_calls": 0, "paid_calls": 0,
               "default_app_integrated": False, "field_sources_compatible": False}
for path, maximum in [("dist/ATLAS.yaml", 2097152), ("dist/schemas/atlas_output_schema.json", 65536)]:
    uri = f"https://raw.githubusercontent.com/mitre-atlas/atlas-data/{COMMIT}/{path}"
    receipt = {"url": uri, "max_bytes": maximum,
               "started_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
               "redirect_hops": 0, "dns_budget_seconds": 2, "credentials": False,
               "authorization": "root additional two fixed new-org GETs"}
    try:
        gateway = NetworkGateway(NetworkPolicy(
            allowed_domains=("raw.githubusercontent.com",), max_response_bytes=maximum,
            allowed_content_types=("text/plain", "application/json", "application/yaml"),
            total_timeout_seconds=22,
        ), max_concurrent_requests=1)
        resolver = CloudflareDohResolver()
        gateway._resolve_addresses = lambda host, budget: resolver(
            host, RequestDeadline(min(budget.expires_at, time.monotonic() + 2))
        )
        response = gateway.fetch(uri, max_redirect_hops=0, deadline=deadline)
        receipt.update(status=response.status_code, bytes=len(response.body),
                       content_type=response.content_type, final_url=response.final_url)
        if response.status_code != 200:
            raise ValueError("http_failure")
        digest = hashlib.sha256(response.body).hexdigest()
        target = CAS / digest
        if target.exists():
            assert target.read_bytes() == response.body
        else:
            target.write_bytes(response.body)
        receipt.update(sha256=digest, cas_path=str(target), result="fetched")
        if path.endswith("ATLAS.yaml"):
            catalogue = parse_atlas_catalogue(response.body, CatalogueProvenance(
                kind="atlas", canonical_uri=uri, snapshot_version=COMMIT, content_sha256=digest,
            ))
            observation.update(content_version=catalogue.content_version,
                               format_version=catalogue.format_version,
                               supported_ids=len(catalogue.supported_ids), source_hash=digest)
        else:
            schema = json.loads(response.body)
            observation["official_schema_sha256"] = digest
            observation["official_schema_id"] = schema.get("$id")
    except Exception as error:
        receipt.update(result="failed", error_code=getattr(error, "code", type(error).__name__))
        if isinstance(error, ValueError):
            observation["parse_error"] = str(error)
    finally:
        receipt["completed_at"] = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
        receipts.append(receipt)
        (RUN / "atlas_new_org_fetch_manifest.json").write_text(json.dumps(receipts, indent=2))
(RUN / "atlas_new_org_parse_observation.json").write_text(json.dumps(observation, indent=2))
print(json.dumps(observation))
raise SystemExit(0 if "supported_ids" in observation else 1)
