"""Four bounded connector requests retain only aggregate observations, never host records."""

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import SecretStr

from ai_intel.assets.hunter_aggregate import HunterAggregateConnector
from ai_intel.assets.quake_aggregate import QuakeAggregateConnector

RUN = Path(__file__).resolve().parent


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def main():
    started = now()
    records = []
    for provider, connector_type in (("hunter", HunterAggregateConnector), ("quake", QuakeAggregateConnector)):
        connector = connector_type(SecretStr(os.environ["DIANZI_AGGREGATE_" + provider.upper() + "_KEY"]), dns_resolver="cloudflare_doh")
        for query_id in ("ollama", "vllm"):
            entry = {"provider": provider, "query_id": query_id, "started_at": now()}
            try:
                observation = connector.collect(query_id)
                entry["observation"] = observation.model_dump(mode="json")
            except Exception as error:
                entry.update(state="probe_failed", error_type=type(error).__name__)
            entry["ended_at"] = now()
            records.append(entry)
            print(json.dumps(entry), flush=True)
    receipt = {"started_at": started, "ended_at": now(), "maximum_search_requests": 4,
               "attempted_connector_calls": 4, "account_requests": 0, "active_scans": 0,
               "model_calls": 0, "fee": "unknown", "raw_responses_saved": False,
               "asset_records_saved": False, "code_sha": "349c5e3ec27196257b98cdfcb63c75fb50157978",
               "scope": "direct reviewed connectors; no PG/worker/API/UI integration validation",
               "observations": records}
    (RUN / "aggregate_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
