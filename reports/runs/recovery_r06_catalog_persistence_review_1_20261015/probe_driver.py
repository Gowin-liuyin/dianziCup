"""Run independent PG assertion probes directly; full pytest gates stay separate."""

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import test_review_pg_probes as probes

failed = 0
for name in sorted(vars(probes)):
    if not name.startswith("test_"):
        continue
    fixture = probes.engine.__wrapped__()
    database = next(fixture)
    with TemporaryDirectory(prefix="dianzi-review-probe-") as directory:
        try:
            getattr(probes, name)(database, Path(directory))
        except BaseException as error:
            failed += 1
            print(json.dumps({"name": name, "outcome": "failed", "error_type": type(error).__name__, "detail": str(error)}), flush=True)
        else:
            print(json.dumps({"name": name, "outcome": "passed"}), flush=True)
        finally:
            try:
                next(fixture)
            except StopIteration:
                pass
print(json.dumps({"total": 7, "failed": failed, "passed": 7 - failed, "coverage": "not measured here; unchanged full pytest gate recorded separately"}))
sys.exit(1 if failed else 0)
