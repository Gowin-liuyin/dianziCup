"""Read at most four fixed AVID public API responses without credentials."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
sys.path.insert(0, str(RUN.parents[2] / "backend" / "src"))

from ai_intel.infrastructure.models.json_output import strict_json_object
from ai_intel.infrastructure.network import (
    NetworkPolicy,
    NetworkPolicyViolation,
    NetworkRequestError,
    create_network_gateway,
)

ZONE = timezone(timedelta(hours=8))


def main() -> int:
    if (RUN / "avid_probe_summary.json").exists():
        raise RuntimeError("This bounded probe already ran")
    gateway = create_network_gateway(
        NetworkPolicy(
            allowed_domains=("api.github.com",),
            max_response_bytes=2097152,
            total_timeout_seconds=15,
            allowed_content_types=("application/json",),
            dns_resolver="cloudflare_doh",
        ),
        max_concurrent_requests=1,
    )
    pending = ["/repos/avidml/avid-db/contents/vulnerabilities/2023?ref=main"]
    records: list[dict[str, object]] = []
    started = time.monotonic()
    previous_start = 0.0
    failures = 0
    while pending and len(records) < 4 and time.monotonic() - started < 70:
        time.sleep(max(0.0, 7 - (time.monotonic() - previous_start)))
        previous_start = time.monotonic()
        path = pending.pop(0)
        label = f"avid_{len(records) + 1:02}"
        record: dict[str, object] = {
            "started_at": datetime.now(ZONE).isoformat(timespec="seconds"),
            "url": "https://api.github.com" + path,
            "credentials_used": False,
            "method": "GET",
            "max_response_bytes": 2097152,
            "timeout_seconds": 15,
            "redirects": 0,
            "retries": 0,
            "dns_resolver": "cloudflare_doh",
            "capability": "probe_only_not_product_wired",
            "redistribution": "AVID repository MIT; raw for internal evidence, no code execution",
        }
        try:
            response = gateway.fetch(str(record["url"]), max_redirect_hops=0)
            (RUN / f"{label}.body").write_bytes(response.body)
            record.update(
                status=response.status_code,
                body_path=f"{label}.body",
                body_sha256=hashlib.sha256(response.body).hexdigest(),
                size_bytes=len(response.body),
                headers=response.redacted_headers,
                final_url=response.final_url,
            )
            failures = 0
            if response.status_code != 200:
                record["stop_reason"] = "HTTP failure; no retry"
                pending.clear()
            elif path.endswith("?ref=main"):
                wrapper = strict_json_object(b'{"entries":' + response.body + b"}", 2097164)
                entries = wrapper["entries"]
                if not isinstance(entries, list):
                    raise ValueError("AVID directory must be an array")
                for entry in entries:
                    if not isinstance(entry, dict):
                        raise ValueError("AVID directory entry must be an object")
                    sha, record_path = entry.get("sha"), entry.get("path")
                    if (
                        entry.get("type") == "file"
                        and isinstance(sha, str)
                        and re.fullmatch(r"[0-9a-f]{40}", sha)
                        and isinstance(record_path, str)
                        and re.fullmatch(r"vulnerabilities/2023/[A-Za-z0-9_-]+\.json", record_path)
                        and len(pending) < 2
                    ):
                        pending.append("/repos/avidml/avid-db/git/blobs/" + sha)
            remaining = response.redacted_headers.get("x-ratelimit-remaining")
            if remaining is not None and remaining.isdigit() and int(remaining) <= 1:
                record["stop_reason"] = "shared anonymous quota nearly exhausted"
                pending.clear()
        except (NetworkRequestError, NetworkPolicyViolation, ValueError) as error:
            failures += 1
            record.update(error_type=type(error).__name__, error_message=str(error))
            if failures >= 2 or isinstance(error, ValueError):
                pending.clear()
        record["ended_at"] = datetime.now(ZONE).isoformat(timespec="seconds")
        records.append(record)
        (RUN / f"{label}.metadata.json").write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps({"label": label, "status": record.get("status"), "size": record.get("size_bytes"), "error": record.get("error_type")}), flush=True)
    (RUN / "avid_probe_summary.json").write_text(
        json.dumps(records, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
