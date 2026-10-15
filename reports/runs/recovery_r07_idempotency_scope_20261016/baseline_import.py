"""Load the exact frozen e61 service blob before unchanged independent probes collect."""

import hashlib
import importlib.util
import sys
from pathlib import Path

SOURCE = Path(__file__).with_name("baseline_job_service.py")
specification = importlib.util.spec_from_file_location("ai_intel.enrichment.job_service", SOURCE)
module = importlib.util.module_from_spec(specification)
sys.modules["ai_intel.enrichment.job_service"] = module
specification.loader.exec_module(module)


def pytest_sessionstart(session):
    assert module.__file__ == str(SOURCE)
    assert not hasattr(module, "ENRICHMENT_IDEMPOTENCY_NAMESPACE_VERSION")
    expected = SOURCE.with_suffix(".sha256").read_text().strip()
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == expected
