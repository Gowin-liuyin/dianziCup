"""Release only this review's named test databases after all connections are closed."""

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

RUN = Path(__file__).resolve().parent
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
names = set()
for path in RUN.glob("*.command.json"):
    receipt = json.loads(path.read_text(encoding="utf-8"))
    name = receipt.get("isolated_database")
    if name:
        assert re.fullmatch(r"test_dianzi_r07_input_review1_[0-9]{4}_[0-9]{6}_[0-9a-f]{5}", name)
        names.add(name)
private = json.loads(subprocess.check_output(["wsl.exe", "-u", "root", "--exec", "cat", "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"], stderr=subprocess.PIPE))
original = make_url(private["TEST_DATABASE_URL"])
assert original.username.startswith("test_") and original.database.startswith("test_dianzi_")
engine = create_engine(original.set(database="postgres"), isolation_level="AUTOCOMMIT")
released = []
with engine.connect() as connection:
    for name in sorted(names):
        assert name != original.database
        active = connection.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE datname=:name"), {"name": name})
        if active:
            raise RuntimeError("owned review database still active")
        connection.execute(text('DROP DATABASE IF EXISTS "' + name + '"'))
        assert connection.scalar(text("SELECT count(*) FROM pg_database WHERE datname=:name"), {"name": name}) == 0
        released.append(name)
engine.dispose()
del private
result = {"started_at": started, "completed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "command": [sys.executable, str(Path(__file__).resolve())], "cwd": str(Path.cwd()), "exit_code": 0, "released_databases": released, "shared_services_untouched": True, "credentials_written": False}
(RUN / "owned_pg_release.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result))
