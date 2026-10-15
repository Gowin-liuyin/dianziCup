"""在唯一自有MinIO supervisor上验证停止重启后的真实对象字节。"""

import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import SecretStr

from ai_intel.infrastructure.minio_store import MinioContentStore

RUN = Path(__file__).resolve().parent


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def main() -> None:
    receipt_path = RUN / "restart_verification.json"
    if receipt_path.exists():
        raise FileExistsError("restart proof already exists")
    private = subprocess.run(
        ["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat",
         "/tmp/dianzi-minio-r02-20261015/private/connection.json"],
        check=True, capture_output=True, text=True, timeout=10,
    )
    configuration = json.loads(private.stdout)

    def new_client() -> MinioContentStore:
        return MinioContentStore(configuration["endpoint"], configuration["bucket"],
                                 SecretStr(configuration["access_key"]),
                                 SecretStr(configuration["secret_key"]),
                                 secure=False, test_mode=True, timeout_seconds=2)

    started = now()
    payload = b"explicit isolated R02 restart test payload 20261015"
    stored = new_client().store_bytes(payload)
    first = json.loads((RUN / "service_segment_1_start.json").read_text())
    (RUN / "service_restart_1.request").write_text(now())
    deadline = time.monotonic() + 30
    verified = False
    while time.monotonic() < deadline:
        if (RUN / "service_segment_2_start.json").exists():
            try:
                verified = new_client().read_verified(stored.content_hash) == payload
            except RuntimeError:
                pass
            if verified:
                break
        time.sleep(0.25)
    second_path = RUN / "service_segment_2_start.json"
    second = json.loads(second_path.read_text()) if second_path.exists() else {}
    result = {"started_at": started, "ended_at": now(), "verified": verified,
              "content_hash": stored.content_hash, "old_pid": first["child_pid"],
              "new_pid": second.get("child_pid"), "different_process": first.get("child_pid") != second.get("child_pid"),
              "scope": "real isolated native MinIO; test content; not external source live"}
    receipt_path.write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
    if not verified or not result["different_process"]:
        raise RuntimeError("object restart persistence was not proven")


if __name__ == "__main__":
    main()
