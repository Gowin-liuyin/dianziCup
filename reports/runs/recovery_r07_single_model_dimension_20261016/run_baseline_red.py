"""Load only the original model_fields module for an explicit baseline-only red run."""

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import ai_intel.enrichment
import pytest

RUN_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(RUN_ROOT.parents[2] / "backend"))
BASELINE_SHA = "63e4cafe1363530eb08cdfe7fec56cfc07a81b8a"
source = subprocess.check_output(
    ["git", "show", f"{BASELINE_SHA}:backend/src/ai_intel/enrichment/model_fields.py"],
    cwd=RUN_ROOT.parents[2],
)
source_path = RUN_ROOT / "baseline_model_fields.py.txt"
source_path.write_bytes(source)
name = "ai_intel.enrichment.model_fields"
specification = importlib.util.spec_from_loader(name, loader=None)
module = importlib.util.module_from_spec(specification)
sys.modules[name] = module
ai_intel.enrichment.model_fields = module
exec(compile(source, str(source_path), "exec"), module.__dict__)
print(json.dumps({"baseline_sha": BASELINE_SHA, "module_sha256": hashlib.sha256(source).hexdigest()}))
sys.exit(pytest.main(sys.argv[1:]))
