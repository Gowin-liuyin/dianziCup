"""Four authorized fixed public GETs, bounded gateway, raw bytes outside the repository."""

import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ai_intel.enrichment.taxonomy_inputs import (
    CatalogueProvenance, parse_atlas_catalogue, parse_cwe_catalogue,
)
from ai_intel.infrastructure.dns_resolver import CloudflareDohResolver
from ai_intel.infrastructure.network import NetworkGateway, NetworkPolicy, RequestDeadline

RUN = Path(__file__).resolve().parent
CAS = Path("D:/dianzi-private/r07-taxonomy-cas")
ZONE = ZoneInfo("Asia/Shanghai")
receipts = []
deadline = RequestDeadline(time.monotonic() + 90)


def now():
    return datetime.now(ZONE).isoformat()


def fetch(label, url, domain, maximum, types):
    receipt = {"label": label, "url": url, "started_at": now(), "max_bytes": maximum,
               "authorization": "root fixed four primary GETs, 90s, no paid/model/scanning",
               "redirect_hops": 0, "dns_budget_seconds": 2, "credentials": False}
    try:
        gateway = NetworkGateway(NetworkPolicy(
            allowed_domains=(domain,), max_response_bytes=maximum,
            allowed_content_types=types, total_timeout_seconds=22,
        ), max_concurrent_requests=1)
        resolver = CloudflareDohResolver()
        gateway._resolve_addresses = lambda host, budget: resolver(
            host, RequestDeadline(min(budget.expires_at, time.monotonic() + 2))
        )
        response = gateway.fetch(url, max_redirect_hops=0, deadline=deadline)
        receipt.update(status=response.status_code, content_type=response.content_type,
                       final_url=response.final_url, bytes=len(response.body))
        if response.status_code != 200:
            raise ValueError("public_source_http_failure")
        digest = hashlib.sha256(response.body).hexdigest()
        CAS.mkdir(parents=True, exist_ok=True)
        path = CAS / digest
        if path.exists():
            assert path.read_bytes() == response.body
        else:
            path.write_bytes(response.body)
        receipt.update(sha256=digest, cas_path=str(path), result="fetched")
        return response.body, digest
    except Exception as error:
        receipt.update(result="failed", error_code=getattr(error, "code", type(error).__name__))
        return None, None
    finally:
        receipt["completed_at"] = now()
        receipts.append(receipt)
        (RUN / "taxonomy_fetch_manifest.json").write_text(
            json.dumps(receipts, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def main():
    commit_raw, _ = fetch("atlas_commit", "https://api.github.com/repos/mitre-atlas/atlas-data/commits/main",
                          "api.github.com", 131072, ("application/json",))
    summary = {"started_at": receipts[0]["started_at"], "model_calls": 0,
               "paid_calls": 0, "mapping_calls": 0, "default_app_integrated": False}
    if commit_raw is not None:
        commit = json.loads(commit_raw)["sha"]
        assert re.fullmatch(r"[0-9a-f]{40}", commit)
        summary["atlas_commit"] = commit
        uri = f"https://raw.githubusercontent.com/mitre/atlas-data/{commit}/dist/ATLAS.yaml"
        raw, digest = fetch("atlas_legacy", uri, "raw.githubusercontent.com", 2097152,
                            ("text/plain", "application/yaml", "text/yaml"))
        if raw is not None:
            try:
                catalogue = parse_atlas_catalogue(raw, CatalogueProvenance(
                    kind="atlas", canonical_uri=uri, snapshot_version=commit, content_sha256=digest,
                ))
                summary["atlas"] = {"content_version": catalogue.content_version,
                                    "format_version": catalogue.format_version,
                                    "supported_ids": len(catalogue.supported_ids),
                                    "source_hash": digest, "deprecated_legacy": True}
            except Exception as error:
                summary["atlas_parse_error"] = str(error) if isinstance(error, ValueError) else type(error).__name__
        fetch("atlas_legacy_schema", f"https://raw.githubusercontent.com/mitre/atlas-data/{commit}/dist/schemas/atlas_output_schema.json",
              "raw.githubusercontent.com", 65536, ("text/plain", "application/json"))
    uri = "https://cwe.mitre.org/data/xml/cwec_v4.19.xml.zip"
    raw, digest = fetch("cwe_4_19", uri, "cwe.mitre.org", 8388608,
                        ("application/zip", "application/octet-stream"))
    if raw is not None:
        try:
            catalogue = parse_cwe_catalogue(raw, CatalogueProvenance(
                kind="cwe", canonical_uri=uri, snapshot_version="4.19", content_sha256=digest,
            ))
            summary["cwe"] = {"content_version": catalogue.content_version,
                              "format_version": catalogue.format_version,
                              "supported_ids": len(catalogue.supported_ids), "source_hash": digest}
        except Exception as error:
            summary["cwe_parse_error"] = str(error) if isinstance(error, ValueError) else type(error).__name__
    summary["completed_at"] = now()
    (RUN / "taxonomy_parse_observation.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary))
    return 0 if "atlas" in summary and "cwe" in summary else 1


if __name__ == "__main__":
    raise SystemExit(main())
