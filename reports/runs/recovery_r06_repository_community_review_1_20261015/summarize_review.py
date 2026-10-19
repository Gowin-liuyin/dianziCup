"""Summarize independent evidence and save exact null-array reproductions."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import asdict
from pathlib import Path

from ai_intel.ingestion.sources.osv import normalize_osv_record

RUN = Path(__file__).resolve().parent


def main() -> None:
    summary: dict[str, object] = {}
    counts = {}
    for path in RUN.glob("*.junit.xml"):
        document = ET.fromstring(path.read_bytes())
        cases = list(document.iter("testcase"))
        failures = [
            case.attrib["name"] for case in cases if case.find("failure") is not None
        ]
        errors = [
            case.attrib["name"] for case in cases if case.find("error") is not None
        ]
        skipped = [
            case.attrib["name"] for case in cases if case.find("skipped") is not None
        ]
        counts[path.name] = {
            "testsuites": [suite.attrib for suite in document.iter("testsuite")],
            "case_count": len(cases),
            "passed": len(cases) - len(failures) - len(errors) - len(skipped),
            "failures": failures,
            "errors": errors,
            "skipped": skipped,
        }
    summary["test_counts"] = counts
    traces = {}
    for path in RUN.glob("cbm_trace_*.log"):
        result = json.loads(path.read_bytes())
        result = result.get("structuredContent") or json.loads(
            result["content"][0]["text"]
        )
        traces[path.stem] = {
            "function": result["function"],
            "callers_total": result["callers_total"],
            "callees_total": result["callees_total"],
            "callers": result["callers"],
        }
    summary["source_only_traces"] = traces
    summary["null_array_reproductions"] = [
        {
            "is_synthetic": True,
            "input": fields,
            "expected": "OsvContractError",
            "actual": asdict(normalize_osv_record(fields)),
        }
        for fields in (
            {"id": "OSV-REVIEW", "aliases": None},
            {"id": "OSV-REVIEW", "related": None},
            {"id": "OSV-REVIEW", "upstream": None},
            {"id": "OSV-REVIEW", "affected": None},
            {"id": "OSV-REVIEW", "affected": [{"ranges": None}]},
            {
                "id": "OSV-REVIEW",
                "affected": [{"ranges": [{"type": "SEMVER", "events": None}]}],
            },
            {"id": "OSV-REVIEW", "affected": [{"versions": None}]},
        )
    ]
    (RUN / "review_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
