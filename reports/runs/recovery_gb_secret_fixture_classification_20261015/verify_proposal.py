"""Run the existing scan and one original regression with an isolated combined table."""

import json
import subprocess
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone

import pytest

from inspect_candidates import ROOT, RUN, security_scan


class TemporaryClassificationInput:
    """Replace only the manifest input in the collected original regression."""

    def pytest_collection_modifyitems(self, items):
        for item in items:
            if item.name != "test_audit_and_sources_carry_no_secret_values_t06_c06":
                continue
            original_loader = item.module.load_fixture_classifications
            item.module.load_fixture_classifications = lambda root, _table: original_loader(root, RUN / "combined_fixture_manifest.json")


started = datetime.now(timezone.utc).isoformat()
classifications = security_scan.load_fixture_classifications(ROOT, RUN / "combined_fixture_manifest.json")
findings = security_scan.scan_repository(ROOT,classifications)
rejected = [asdict(item) for item in findings if item.category not in security_scan.SAFE_CATEGORIES]
scan_result = {"started_at":started,"ended_at":datetime.now(timezone.utc).isoformat(),"head":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),"exact_secret_scan":"not_run","classification_count":len(classifications),"finding_count":len(findings),"category_counts":dict(Counter(item.category for item in findings)),"rejected_count":len(rejected),"rejected":rejected}
(RUN / "combined_scan.json").write_text(json.dumps(scan_result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
arguments=["tests/security/test_t06_authentication_and_scope.py::test_audit_and_sources_carry_no_secret_values_t06_c06","--no-cov","-q",f"--junitxml={RUN / 'targeted_t06.xml'}"]
test_started=datetime.now(timezone.utc).isoformat()
test_exit=pytest.main(arguments,plugins=[TemporaryClassificationInput()])
receipt={"command":["uv","run","--frozen","--extra","semantic","python",str(__file__)],"pytest_arguments":arguments,"cwd":str(ROOT / "backend"),"started_at":test_started,"ended_at":datetime.now(timezone.utc).isoformat(),"exit_code":int(test_exit),"head":scan_result["head"],"fixture_input":"temporary combined manifest; shared source manifest untouched","scan":scan_result}
(RUN / "targeted_t06.receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"rejected_count":len(rejected),"category_counts":scan_result["category_counts"],"targeted_exit_code":int(test_exit),"exact_secret_scan":"not_run"}))
raise SystemExit(int(test_exit) or (1 if rejected else 0))
