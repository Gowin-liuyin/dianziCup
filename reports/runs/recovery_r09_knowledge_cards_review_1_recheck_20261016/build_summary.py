"""汇总命令/JUnit与当前调用图；相同复跑不另计验收分母。"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

RUN = Path(__file__).resolve().parent


def junit(label):
    path = RUN / f"{label}.xml"
    if not path.exists():
        return None, set()
    document = ET.parse(path)
    counts = {key: sum(int(suite.get(key, "0")) for suite in document.findall(".//testsuite")) for key in ("tests", "failures", "errors", "skipped")}
    cases = {(case.get("classname"), case.get("name")) for case in document.findall(".//testcase")}
    return counts, cases


commands = []
for path in RUN.glob("*.command.json"):
    item = json.loads(path.read_bytes())
    item["label"] = path.name.removesuffix(".command.json")
    item["junit"], _ = junit(item["label"])
    commands.append(item)
commands.sort(key=lambda item: item["started_at"])
corpus = set().union(*(junit(label)[1] for label in ("unit_regression", "contract_regression", "security_regression")))
assert len(corpus) == 380
assert junit("focused")[1] <= corpus
assert junit("original_t22")[1] <= corpus
assert len(junit("independent_17")[1]) == 17
assert len(junit("shared_17")[1]) == 17
assert junit("shared_17")[1].isdisjoint(corpus)
assert all(item["exit_code"] == 0 for item in commands)
graphs = {}
for name in ("card", "generation", "grounding", "candidate"):
    envelope = json.loads((RUN / f"cbm_{name}_trace.stdout.log").read_bytes())
    assert not envelope.get("isError", False)
    content = envelope["structuredContent"]
    graphs[name] = {"qualified_name": content["function"], "callers_total": content["callers_total"], "callees_total": content["callees_total"]}
assert graphs["card"]["callers_total"] == 0
result = {"commands": commands, "distinct_regression_cases": 380, "focused_cases_inside_regression": 66, "original_t22_inside_regression": 6, "independent_cases": 17, "shared_new_cases": 17, "exact_card_cases": 1, "graphs": graphs, "real_pg_sessions": 0, "real_model_calls": 0, "real_external_requests": 0}
(RUN / "command_index.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
print(json.dumps({key: value for key, value in result.items() if key != "commands"}, ensure_ascii=False, indent=2))
for item in commands:
    print(f"{item['label']}: exit={item['exit_code']} junit={item['junit']} {item['started_at']} -> {item['finished_at']}")
