"""只核对本工作包隔离库的临时schema，保留库与私密连接供独立review。"""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text

configuration = json.loads(Path("/tmp/dianzi-r04-api-20261015/connection.json").read_text())
engine = create_engine(configuration["TEST_DATABASE_URL"])
with engine.connect() as connection:
    assert connection.scalar(text("SELECT current_database()")) == "test_dianzi_r04_api_20261015"
    remaining = connection.scalar(text(
        "SELECT count(*) FROM pg_namespace WHERE nspname LIKE 'test_r04_api_%'"
    ))
engine.dispose()
receipt = {"checked_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
           "own_database": "test_dianzi_r04_api_20261015", "remaining_owned_test_schemas": remaining,
           "background_processes_started": 0, "engine_closed": True}
Path(__file__).with_suffix(".json").write_text(json.dumps(receipt, indent=2))
print(json.dumps(receipt))
