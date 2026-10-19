"""Report the actual legacy schema errors without changing source bytes or schema."""

import hashlib
import json
from pathlib import Path

import jsonschema
import yaml

CAS = Path("D:/dianzi-private/r07-taxonomy-cas")
RUN = Path(__file__).resolve().parent
DATA_HASH = "c9c23971d0db07e2782423d795a20e78d5c2c9bcdc78fc67e24530657daaec41"
SCHEMA_HASH = "17349bf6127b69a2b366aa6c18a8a9d0034545c88186e8120269f94b51f263f1"
raw = (CAS / DATA_HASH).read_bytes()
schema_bytes = (CAS / SCHEMA_HASH).read_bytes()
assert hashlib.sha256(raw).hexdigest() == DATA_HASH
assert hashlib.sha256(schema_bytes).hexdigest() == SCHEMA_HASH
schema = json.loads(schema_bytes)
validator_class = jsonschema.validators.validator_for(schema)
validator_class.check_schema(schema)
errors = list(validator_class(schema).iter_errors(yaml.safe_load(raw)))
result = {"atlas_raw_sha256": DATA_HASH, "schema_raw_sha256": SCHEMA_HASH, "full_schema_passed": not errors, "error_count": len(errors), "errors": [{"path": list(error.path), "validator": error.validator, "message": error.message, "context_count": len(error.context)} for error in errors]}
(RUN / "independent_official_schema_observation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: value for key, value in result.items() if key != "errors"}))
raise SystemExit(1 if errors else 0)
