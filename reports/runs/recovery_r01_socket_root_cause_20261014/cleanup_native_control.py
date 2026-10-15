"""Remove only the control socket created by this diagnostic run."""

import ctypes
import json
from ctypes import wintypes
from datetime import datetime
from pathlib import Path


run_directory = Path(__file__).resolve().parent
control_path = run_directory / "control-213024.sock"
assert control_path.parent.resolve() == run_directory
stat = control_path.lstat()
assert stat.st_size == 0 and stat.st_reparse_tag == 0x80000023
kernel = ctypes.WinDLL("kernel32", use_last_error=True)
kernel.DeleteFileW.argtypes = [wintypes.LPCWSTR]
kernel.DeleteFileW.restype = wintypes.BOOL
success = kernel.DeleteFileW(str(control_path))
print(json.dumps({"recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                  "path": str(control_path), "created_by": "native_bind_control 21:30:24+08:00",
                  "delete_success": bool(success),
                  "winerror": 0 if success else ctypes.get_last_error()}, indent=2))
assert success
