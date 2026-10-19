"""Bind the reviewed source supervisor to a new run ID without modifying its frozen source."""

from __future__ import annotations

import json
import os
import runpy
import sys
from datetime import datetime

from configuration import CORE, OPS, RUN_ID, ZONE, require_activation, require_start_window


def main() -> None:
    activation = require_activation()
    require_start_window(datetime.now(ZONE))
    sys.path.insert(0, str(CORE))
    namespace = runpy.run_path(str(CORE / "controlled_supervise.py"))
    if namespace.get("RUN_ID") != RUN_ID:
        raise ValueError("fixed new core run binding differs")
    identity_namespace = runpy.run_path(str(CORE / "owned_stop_watcher.py"))
    identity_function = identity_namespace["current_windows_identity"]
    if not callable(identity_function):
        raise TypeError("frozen Windows identity function required")
    identity = identity_function()
    pending = OPS / "source_identity.pending"
    with pending.open("x", encoding="utf-8") as output:
        json.dump({"run_id": RUN_ID, "nonce": activation["nonce"], **identity}, output)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
    pending.replace(OPS / "source_identity.json")
    entry = namespace["main"]
    if not callable(entry):
        raise TypeError("frozen supervisor entry required")
    entry()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(
            json.dumps(
                {
                    "error_type": type(error).__name__,
                    "details": "withheld",
                    "startup_status": "unknown_check_owned_receipts",
                }
            )
        )
        raise SystemExit(1) from None
