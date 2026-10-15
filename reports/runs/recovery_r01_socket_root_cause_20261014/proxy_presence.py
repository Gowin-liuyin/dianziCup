"""Check only whether inherited network proxy keys are present, without exposing values."""

import json
import os
from datetime import datetime


keys = ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy", "ALL_PROXY", "all_proxy")
print(json.dumps({"recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                  "proxy_key_present": {key: bool(os.environ.get(key)) for key in keys}}, indent=2))
