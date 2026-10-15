"""Check host AF_UNIX support using a new artifact inside this run directory."""

import json
import socket
from datetime import datetime
from pathlib import Path


run_directory = Path(__file__).resolve().parent
socket_path = run_directory / ("af-unix-" + datetime.now().strftime("%H%M%S") + ".sock")
backup_path = socket_path.with_suffix(".backup.sock")
assert socket_path.parent == run_directory
assert not socket_path.exists() and not backup_path.exists()
result: dict[str, str | int | bool | None] = {
    "recorded_at": datetime.now().astimezone().isoformat(),
    "socket_path": str(socket_path),
    "backup_path": str(backup_path),
    "created": False,
    "renamed": False,
    "python_exposes_af_unix": hasattr(socket, "AF_UNIX"),
}
if not result["python_exposes_af_unix"]:
    result["error"] = "This Python build does not expose AF_UNIX; host socket behavior was not exercised."
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(2)
try:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.settimeout(5)
        listener.bind(str(socket_path))
        result["created"] = True
    socket_path.rename(backup_path)
    result["renamed"] = True
except OSError as error:
    result["error"] = str(error)
    result["errno"] = error.errno
    result["winerror"] = getattr(error, "winerror", None)
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(0 if result["created"] and result["renamed"] else 1)
