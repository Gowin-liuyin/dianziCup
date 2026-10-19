"""Load the frozen pre-change module in this process only for a baseline red check."""

import hashlib
import importlib.util
import json
import subprocess
import sys

import ai_intel.enrichment
import pytest

from review_run import ROOT, RUN

sys.path.insert(0, str(ROOT / "backend"))
source = subprocess.check_output(["git", "show",
    "63e4cafe1363530eb08cdfe7fec56cfc07a81b8a:backend/src/ai_intel/enrichment/model_fields.py"], cwd=ROOT)
assert hashlib.sha256(source).hexdigest() == "3a855b58d843e2aaecc42db4a3f86341b0b438f18c90e28e9965062c77027faa"
source_path = RUN / "independent_baseline_model_fields.py.txt"
source_path.write_bytes(source)
name = "ai_intel.enrichment.model_fields"
spec = importlib.util.spec_from_loader(name, loader=None)
module = importlib.util.module_from_spec(spec)
sys.modules[name] = module
ai_intel.enrichment.model_fields = module
exec(compile(source, str(source_path), "exec"), module.__dict__)
print(json.dumps({"baseline_sha": "63e4cafe1363530eb08cdfe7fec56cfc07a81b8a",
                  "module_sha256": hashlib.sha256(source).hexdigest()}))
raise SystemExit(pytest.main(sys.argv[1:]))
