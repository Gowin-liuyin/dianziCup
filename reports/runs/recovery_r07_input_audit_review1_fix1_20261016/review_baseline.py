"""Load all four exact predecessor modules while retaining the same original test and input."""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

RUN = Path(__file__).resolve().parent
receipt = json.loads((RUN / 'frozen_copies.json').read_bytes())
for row in receipt['baseline_modules']:
    name = Path(row['path']).stem
    source = RUN / 'baseline' / (name + '.py')
    assert hashlib.sha256(source.read_bytes()).hexdigest() == row['raw_sha256']
    module_name = 'ai_intel.enrichment.' + name
    specification = importlib.util.spec_from_file_location(module_name, source)
    module = importlib.util.module_from_spec(specification)
    sys.modules[module_name] = module
    specification.loader.exec_module(module)
    import ai_intel.enrichment
    setattr(ai_intel.enrichment, name, module)
assert not hasattr(sys.modules['ai_intel.enrichment.job_service'], '_versioned_execution_policy')
