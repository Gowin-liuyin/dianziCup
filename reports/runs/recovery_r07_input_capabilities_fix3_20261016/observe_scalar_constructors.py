"""Compare bounded synthetic builtin scalars at the installed mature constructor boundary."""

import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))

import yaml
from tests.unit.test_r07_input_capabilities import ATLAS_YAML, INVALID_YAML_SCALARS, VALID_YAML_SCALARS, provenance
from ai_intel.enrichment.taxonomy_inputs import parse_atlas_catalogue

RUN = Path(__file__).resolve().parent
phase = sys.argv[1]
assert phase in {"before", "after"}
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
taxonomy_source_sha = "working_tree"
parser = parse_atlas_catalogue
if phase == "before":
    taxonomy_source_sha = "7aeb85ae8277c048fb762dbc705436602cb18f9d"
    frozen_bytes = subprocess.check_output([
        "git", "show", taxonomy_source_sha + ":backend/src/ai_intel/enrichment/taxonomy_inputs.py",
    ], cwd=RUN.parents[2])
    frozen_path = RUN / "frozen_7a_taxonomy_inputs.py"
    frozen_path.write_bytes(frozen_bytes)
    specification = importlib.util.spec_from_file_location("r07_taxonomy_7a_probe", frozen_path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    parser = module.parse_atlas_catalogue
cases = []
for scalar in (*INVALID_YAML_SCALARS, *VALID_YAML_SCALARS, "!!binary Zm9v", "!!binary not-base64", "!!binary '中文'"):
    observation = {"synthetic_scalar": scalar}
    try:
        value = yaml.safe_load("metadata: " + scalar)
        observation["native_result"] = type(value["metadata"]).__name__
    except (ValueError, KeyError, AttributeError, IndexError, OverflowError, yaml.YAMLError) as error:
        observation["native_error"] = type(error).__name__
    for position in ("key", "value"):
        suffix = f"\nmetadata:\n  {scalar}: fixture\n" if position == "key" else f"\nmetadata: {scalar}\n"
        raw = ATLAS_YAML + suffix.encode()
        try:
            result = parser(raw, provenance(raw, "atlas"))
            observation[position] = {"members": len(result.entries)}
        except (ValueError, KeyError, AttributeError, IndexError, OverflowError, yaml.YAMLError) as error:
            observation[position] = {"error_type": type(error).__name__, "code": str(error) if type(error).__name__ == "TaxonomyInputError" else None}
    cases.append(observation)
constructor_file = Path(yaml.__file__).with_name("constructor.py")
record = {"phase": phase, "taxonomy_source_sha": taxonomy_source_sha, "started_at": started,
          "completed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
          "yaml_version": yaml.__version__, "constructor_path": str(constructor_file),
          "constructor_sha256": hashlib.sha256(constructor_file.read_bytes()).hexdigest(),
          "network_requests": 0, "model_calls": 0, "cases": cases}
(RUN / ("scalar_constructor_" + phase + ".json")).write_text(json.dumps(record, indent=2), encoding="utf-8")
print(json.dumps({key: value for key, value in record.items() if key != "cases"}))
