"""Read sizes only; choose a free isolated logical DB without deleting any existing key."""

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from redis import Redis

RUN = Path(__file__).resolve().parent
private = subprocess.run(["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat", "/tmp/dianzi-r04-live-20261015/private/runtime_8f6bd9.json"], capture_output=True, text=True, check=True, timeout=10)
configuration = json.loads(private.stdout)
sizes = {}
for number in range(16):
    url = re.sub(r"/[0-9]+$", "/" + str(number), configuration["environment"]["REDIS_URL"])
    client = Redis.from_url(url, socket_timeout=3, socket_connect_timeout=3)
    sizes[str(number)] = client.dbsize()
    client.close()
receipt = {"observed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "read_only": True, "sizes": sizes, "no_key_names_or_values_read": True, "keys_deleted": 0}
(RUN / "redis_precheck.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt))
