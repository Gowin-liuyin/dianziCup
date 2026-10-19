"""Name actual pytest phases without logging credentials or payloads."""

import json
import os
from pathlib import Path


def pytest_runtest_logreport(report):
    Path(os.environ["R18_REVIEW_PHASE_FILE"]).write_text(
        json.dumps({"nodeid": report.nodeid, "phase": report.when, "outcome": report.outcome}),
        encoding="utf-8",
    )


def pytest_runtest_logstart(nodeid, location):
    Path(os.environ["R18_REVIEW_PHASE_FILE"]).write_text(
        json.dumps({"nodeid": nodeid, "phase": "setup"}), encoding="utf-8"
    )
