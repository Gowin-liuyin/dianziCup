"""Import independently verified lifecycle fixes and test-only isolation improvements."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import batch13_checks_helper as checks

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
SOURCE = "dbf9927206cb3ce7aa55f34a8c828771285ef365"
ORIGINAL = "f3c2e41e31fd5b0f1be004b379f5ed775c95f287"
paths = [
    "backend/migrations/env.py",
    "backend/src/ai_intel/infrastructure/database.py",
    "backend/tests/unit/test_r01_migration_engine_disposal.py",
    "backend/tests/integration/test_r01_migration_engine_disposal_pg.py",
    "backend/tests/unit/test_r01_migration_pg_helpers.py",
]
manifest = []
for relative in paths:
    if relative in paths[:2]:
        assert subprocess.check_output(["git", "show", "HEAD:" + relative], cwd=ROOT) == subprocess.check_output(["git", "show", ORIGINAL + ":" + relative], cwd=ROOT)
        subprocess.run(["git", "diff", "--exit-code", "--", relative], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    target = ROOT / relative
    data = subprocess.check_output(["git", "show", SOURCE + ":" + relative], cwd=ROOT)
    if relative not in paths[:2]:
        assert not target.exists()
    target.write_bytes(data)
    manifest.append({"path": relative, "source_sha": SOURCE, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
stamp = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
(RUN / "pool_lifecycle_batch14_inputs.json").write_text(json.dumps({"recorded_at": stamp, "production_source_qualified": "912d8b381eaab9260ead30d68f49b88fa8078384", "test_only_fix_source": SOURCE, "files": manifest, "source_observation_product": "912d8b381eaab9260ead30d68f49b88fa8078384", "whole_task_accepted": False}, indent=2) + "\n", encoding="utf-8", newline="\n")
checks.QUALIFIED = SOURCE
code = checks.execute("pool_lifecycle_batch14_unit", [checks.PYTHON, "-m", "pytest", "tests/unit/test_r01_migration_engine_disposal.py", "tests/unit/test_r01_migration_pg_helpers.py", "tests/contract/test_r01_migration_configuration.py", "-q", "--no-cov", "--junitxml=" + str(RUN / "pool_lifecycle_batch14_unit.xml")])
raise SystemExit(code)
