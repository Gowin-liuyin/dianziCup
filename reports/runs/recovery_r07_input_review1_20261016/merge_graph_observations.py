"""Verify exact testcase coverage across a fixture setup retry without inventing an execution."""

import json
from pathlib import Path
from xml.etree import ElementTree

RUN = Path(__file__).resolve().parent
FIRST = "owned_7aeb85_graph_pg_copies"
RETRY = "owned_7aeb85_graph_pg_copies_retry"


def cases(stem):
    result = {}
    for case in ElementTree.parse(RUN / (stem + ".xml")).findall(".//testcase"):
        key = (case.get("classname", "").split(".")[-1], case.get("name"))
        assert key not in result
        outcome = "failed" if case.find("failure") is not None else "error" if case.find("error") is not None else "skipped" if case.find("skipped") is not None else "passed"
        result[key] = outcome
    return result


initial, retry = cases(FIRST), cases(RETRY)
assert len(initial) == 112 and len(retry) == 33
initial_errors = {key for key, outcome in initial.items() if outcome == "error"}
initial_passed = {key for key, outcome in initial.items() if outcome == "passed"}
assert initial_errors == set(retry) and all(outcome == "passed" for outcome in retry.values())
assert len(initial_passed) == 79 and not (initial_passed & set(retry))
final = {**initial, **retry}
assert len(final) == 112 and set(final.values()) == {"passed"}
result = {"observation_type": "testcase_outcome_union_not_a_new_command", "source_sha": "7aeb85ae8277c048fb762dbc705436602cb18f9d", "initial_receipt": FIRST + ".command.json", "retry_receipt": RETRY + ".command.json", "initial_passed": 79, "initial_setup_errors": 33, "retry_passed": 33, "final_unique_passed": 112, "final_failed": 0, "final_errors": 0, "final_skipped": 0, "exact_missing_testcase_ids_replayed": True, "outcomes": [{"module": key[0], "name": key[1], "outcome": outcome} for key, outcome in sorted(final.items())]}
(RUN / "owned_graph_case_union.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: value for key, value in result.items() if key != "outcomes"}))
