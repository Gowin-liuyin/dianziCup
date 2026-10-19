"""Verify the generated report against fixed source and actual regression artifacts."""

from __future__ import annotations

import hashlib
import json
import subprocess
import xml.etree.ElementTree as element_tree
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
SOURCE = "6d85742b0114cc5e304e88b2aa930755ccce9bc9"


if __name__ == "__main__":
    current = (
        subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, check=True, timeout=30
        )
        .stdout.decode()
        .strip()
    )
    assert current == SOURCE
    suites = element_tree.parse(RUN / "original99_plus9_plus65_and_new.xml").getroot()
    counts = {
        name: sum(int(s.attrib.get(name, "0")) for s in suites.iter("testsuite"))
        for name in ("tests", "failures", "errors", "skipped")
    }
    assert counts == {"tests": 230, "failures": 0, "errors": 0, "skipped": 0}
    report = ROOT / "reports/tasks/R18-sdk-client-fix1.md"
    assert SOURCE in report.read_text(encoding="utf-8")
    identity = json.loads((RUN / "source_identity.json").read_bytes())
    assert identity["source_sha"] == SOURCE
    for entry in identity["files"]:
        assert (
            hashlib.sha256((ROOT / entry["path"]).read_bytes()).hexdigest() == entry["raw_sha256"]
        )
    upstream = json.loads((RUN / "protected_upstream.json").read_bytes())
    assert [entry["member_count"] for entry in upstream["protected"]] == [86, 83]
    observations = json.loads((RUN / "fixed_cli_raw_observations.json").read_bytes())
    assert len(observations["cases"]) == 6
    assert all(
        entry["exit_code"] == 2 and entry["complete_json"] for entry in observations["cases"]
    )
    print(json.dumps({"source_sha": SOURCE, "tests": counts, "report_verified": True}))
