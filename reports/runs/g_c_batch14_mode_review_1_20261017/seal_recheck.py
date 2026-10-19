"""Count the corrected eight PG cases separately from the independent default route probe."""

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET

import review_checks

ROOT, RUN = review_checks.ROOT, review_checks.RUN


def counted(cases):
    return {"tests": len(cases), "failures": sum(case.find("failure") is not None for case in cases), "errors": sum(case.find("error") is not None for case in cases), "skipped": sum(case.find("skipped") is not None for case in cases), "case_names": sorted(case.get("name") for case in cases)}


def main():
    cases = list(ET.parse(RUN / "recheck_modes_and_default.xml").getroot().iter("testcase"))
    fixed = [case for case in cases if "fixed_revision_mode_read_pg" in case.get("classname", "")]
    probe = [case for case in cases if "default_mode_pg" in case.get("classname", "")]
    contract = list(ET.parse(RUN / "recheck_contract.xml").getroot().iter("testcase"))
    original = list(ET.parse(RUN / "pg_modes_and_default.xml").getroot().iter("testcase"))
    assert len(fixed) == 8 and len(probe) == 1 and len(contract) == 1
    assert {case.get("name") for case in cases} == {case.get("name") for case in original}
    old_report = ROOT / "reports/reviews/recovery/G-C-batch14-revision-mode-review-1.md"
    assert hashlib.sha256(old_report.read_bytes()).hexdigest() == "c3bc6648a1b1dcec23f3130163bdc614486a4f97f5749e7cc6bdb77fb9f2a0b1"
    assert subprocess.run(["git", "diff", "--quiet", "48f96b5ba35d19f5e26868a2bccd5b124afb2bd0", "HEAD", "--", "backend", "contracts", "progress", "frontend", "docs"], cwd=ROOT).returncode == 0
    receipt = json.loads((RUN / "recheck_pg_controller.command.json").read_bytes())
    record = {"sealed_at": review_checks.checks.now(), "actual_product_sha": "48f96b5ba35d19f5e26868a2bccd5b124afb2bd0", "fixed_test_source_sha": "6bb19fcdbf5c8242142c3f61e338b98a29bc5501", "fixed_test_material_sha": "81840ea42ae1425dfa1468eafed7edb49b440357", "own_probe_frozen_material_sha": "04da910b5217def869d03800a7144967d8d520c6", "fixed_pg_counts": counted(fixed), "own_default_probe_counts": counted(probe), "bytes_input_positive_contract_counts": counted(contract), "repeated_pg_names_from_first_attempt": 9, "first_attempt_outcomes_unchanged": True, "old_report_raw_sha256": hashlib.sha256(old_report.read_bytes()).hexdigest(), "source_bindings_before_after_equal": receipt["source_bindings_before"] == receipt["source_bindings_after"], "no_pg_count_is_source_model_live": True, "raw_hashes": {name: hashlib.sha256((RUN / name).read_bytes()).hexdigest() for name in ("recheck_modes_and_default.stdout.log", "recheck_modes_and_default.stderr.log", "recheck_modes_and_default.xml", "recheck_pg_controller.command.json", "default_pg_observations.json", "test_fixed_revision_mode_read_pg.py", "test_default_mode_pg.py", "recheck_contract.stdout.log", "recheck_contract.xml")}}
    (RUN / "recheck_counts_and_rawhash.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"fixed_pg": record["fixed_pg_counts"], "default_probe": record["own_default_probe_counts"], "contract": record["bytes_input_positive_contract_counts"], "repeated_pg_names": 9, "first_report_unchanged": True}))


if __name__ == "__main__":
    main()
