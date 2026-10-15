"""Freeze independent fixture observations, counts and import origins."""

import inspect
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

from pytest import MonkeyPatch

import ai_intel.answering.grounding as grounding
from ai_intel.answering.contracts import GroundedAnswerFailure
from test_independent_grounded_probes import citation, client_for, output, verdict

run = Path(__file__).resolve().parent
cases = [
    ("产品A已在1.2.3修复。产品B是否受影响未知。", "产品A已在1.2.3修复。"),
    ("产品A已在1.2.3修复。产品B不受影响。", "产品A已在1.2.3修复。"),
    ("产品A受影响。产品B不受影响。", "产品A受影响。"),
    ("产品A不受影响。产品B是否受影响未知。", "产品A不受影响。"),
]
observations = []
for source, selected in cases:
    with MonkeyPatch.context() as monkeypatch:
        client, calls = client_for(monkeypatch, [output(selected, selected), {"verdicts": [verdict()]}])
        try:
            grounding.generate_grounded_answer(client, "产品A的状态是什么？", (citation(source),))
        except GroundedAnswerFailure as failure:
            observations.append({
                "source": source,
                "selected_quote_and_claim": selected,
                "code": failure.code,
                "wire_calls": len(calls),
                "retained_attempts": len(failure.attempts),
                "attempt_outcomes": [attempt.outcome for attempt in failure.attempts],
                "expected": "two calls and a grounded draft for product A; preserve product B context for verification",
            })

counts = {}
for file in run.glob("*.xml"):
    root = ElementTree.parse(file).getroot()
    suites = root.findall("testsuite") if root.tag == "testsuites" else [root]
    counts[file.name] = {
        key: sum(int(suite.attrib.get(key, 0)) for suite in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    counts[file.name]["classes"] = dict(Counter(case.attrib.get("classname", "") for suite in suites for case in suite.findall("testcase")))

coverage = json.loads((run / "unit_coverage.json").read_text(encoding="utf-8"))
summary = {
    "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    "code_sha": "c1804d0a38cd4e451b801f1ec88df9c3c47629e0",
    "cwd": str(Path.cwd()),
    "import_origin": inspect.getfile(grounding),
    "tests": counts,
    "coverage_totals": coverage["totals"],
    "coverage_source_files": list(coverage["files"]),
    "observations": observations,
    "real_product_provider_calls": 0,
    "fee": "unknown",
}
(run / "review_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"recorded_at": summary["recorded_at"], "import_origin": summary["import_origin"], "coverage": summary["coverage_totals"], "observations": observations}, ensure_ascii=False))
