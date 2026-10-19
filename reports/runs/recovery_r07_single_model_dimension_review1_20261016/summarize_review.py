"""Read independent command receipts and JUnit counts without inventing missing results."""

import datetime
import json
import xml.etree.ElementTree as ET

from review_run import RUN

results = []
for path in sorted(RUN.glob("*.command.json")):
    receipt = json.loads(path.read_text(encoding="utf-8"))
    entry = {"label": path.name.removesuffix(".command.json"), **receipt}
    junit = RUN / (entry["label"] + ".xml")
    if junit.exists():
        suites = list(ET.parse(junit).iter("testsuite"))
        entry["junit"] = {key: sum(int(suite.attrib.get(key, "0")) for suite in suites)
                          for key in ("tests", "failures", "errors", "skipped")}
        entry["junit"]["passed"] = entry["junit"]["tests"] - sum(entry["junit"][key] for key in ("failures", "errors", "skipped"))
    results.append(entry)
summary = {"recorded_at_shanghai": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
           "checks": results, "scope": "independent offline unit/contract/security review only",
           "not_run": ["integration", "frontend", "e2e", "live", "manual"]}
(RUN / "review_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
for entry in results:
    print(entry["label"], entry["exit_code"], entry.get("junit", {}), entry["started_at_shanghai"], entry["ended_at_shanghai"])
