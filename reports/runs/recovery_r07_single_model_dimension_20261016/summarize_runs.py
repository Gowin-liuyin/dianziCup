"""Read receipts and JUnit counts; do not infer passes from the wrapper exit."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

RUN_ROOT = Path(__file__).resolve().parent
results = []
for receipt_path in sorted(RUN_ROOT.glob("*.command.json")):
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    name = receipt_path.name.removesuffix(".command.json")
    result = {"name": name, **receipt}
    junit = RUN_ROOT / f"{name}.xml"
    if junit.exists():
        suites = ET.parse(junit).getroot().findall("testsuite")
        counts = {
            key: sum(int(suite.attrib.get(key, 0)) for suite in suites)
            for key in ("tests", "failures", "errors", "skipped")
        }
        counts["passed"] = counts["tests"] - sum(
            counts[key] for key in ("failures", "errors", "skipped")
        )
        result["junit"] = counts
    results.append(result)
(RUN_ROOT / "run_summary.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
)
print(json.dumps([{key: row[key] for key in ("name", "exit_code", "junit") if key in row} for row in results]))
