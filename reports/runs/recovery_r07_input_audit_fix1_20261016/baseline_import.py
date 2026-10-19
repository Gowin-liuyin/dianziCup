"""Load the exact frozen service blob to distinguish an existing predecessor regression."""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

RUN = Path(__file__).resolve().parent
source = RUN / "baseline_job_service.py"
receipt = json.loads((RUN / "baseline_source_receipt.json").read_bytes())
assert hashlib.sha256(source.read_bytes()).hexdigest() == receipt["raw_sha256"]
name = "ai_intel.enrichment.job_service"
specification = importlib.util.spec_from_file_location(name, source)
module = importlib.util.module_from_spec(specification)
sys.modules[name] = module
specification.loader.exec_module(module)
import ai_intel.enrichment
ai_intel.enrichment.job_service = module
assert not hasattr(module, "_versioned_execution_policy")
