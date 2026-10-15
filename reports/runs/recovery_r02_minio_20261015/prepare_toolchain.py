"""只在项目外下载并校验官方portable Go，供已批准MinIO隔离构建使用。"""

import hashlib
import json
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def main() -> None:
    """有界下载，不安装系统Go、不改PATH/证书校验或现有缓存。"""
    started = now()
    deadline = time.monotonic() + 180
    with urllib.request.urlopen("https://go.dev/dl/?mode=json", timeout=20) as response:
        releases = json.load(response)
    release = next(item for item in releases if item.get("stable"))
    archive = next(item for item in release["files"] if item["os"] == "linux"
                   and item["arch"] == "amd64" and item["kind"] == "archive")
    if not 0 < archive["size"] < 100 * 1024 * 1024:
        raise ValueError("official toolchain size outside approved download bound")
    cache = Path.home() / ".codex/cache/dianzi/minio-r02-20261015"
    cache.mkdir(parents=True, exist_ok=True)
    destination = cache / archive["filename"]
    if destination.exists():
        raise FileExistsError("toolchain archive already exists; verify it separately")
    checksum = hashlib.sha256()
    received = 0
    with urllib.request.urlopen("https://go.dev/dl/" + archive["filename"], timeout=30) as source:
        with destination.open("xb") as output:
            while chunk := source.read(512 * 1024):
                received += len(chunk)
                if received > archive["size"] or time.monotonic() > deadline:
                    raise TimeoutError("bounded toolchain download exceeded size or time")
                output.write(chunk)
                checksum.update(chunk)
    if received != archive["size"] or checksum.hexdigest() != archive["sha256"]:
        raise ValueError("official toolchain checksum/size mismatch; do not execute")
    receipt = {"started_at": started, "ended_at": now(), "metadata_url": "https://go.dev/dl/?mode=json",
               "source_url": "https://go.dev/dl/" + archive["filename"], "version": release["version"],
               "expected_sha256": archive["sha256"], "actual_sha256": checksum.hexdigest(),
               "size_bytes": received, "archive_path": str(destination), "status": "verified_download",
               "installation": "not installed; extraction/build are separate bounded steps"}
    (Path(__file__).parent / "toolchain_download.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
