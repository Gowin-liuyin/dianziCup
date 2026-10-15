"""主控提交快照与已授权实际秘密精确比较；只输出路径与匹配数量。"""

import gzip
import io
import json
import os
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo


def expand_gzip_log(blob: bytes, maximum_bytes: int = 64 * 1024 * 1024) -> bytes:
    """压缩日志也扫描原始内容；超出有界内存预算时阻断而不略过。"""
    with gzip.GzipFile(fileobj=io.BytesIO(blob)) as stream:
        expanded = stream.read(maximum_bytes + 1)
    if len(expanded) > maximum_bytes:
        raise ValueError("compressed evidence exceeds scan limit")
    return expanded


assert expand_gzip_log(gzip.compress(b"scanner synthetic boundary")) == b"scanner synthetic boundary"

clock = ZoneInfo("Asia/Shanghai")
started_at = datetime.now(clock).isoformat(timespec="seconds")
secret_names = (
    "DIANZI_SCAN_DEEPSEEK_API_KEY",
    "DIANZI_SCAN_HUNTER_API_KEY",
    "DIANZI_SCAN_FOFA_API_KEY",
    "DIANZI_SCAN_QUAKE_API_KEY",
    "DIANZI_SCAN_ZOOMEYE_API_KEY",
    "DIANZI_SCAN_TEST_PASSWORD",
)
assert all(os.environ.get(name) for name in secret_names), "required secret references unavailable"
optional_names = (
    "DIANZI_SCAN_PG_PASSWORD", "DIANZI_SCAN_MINIO_ACCESS_KEY", "DIANZI_SCAN_MINIO_SECRET_KEY"
)
secret_bytes = tuple(
    os.environ[name].encode() for name in (*secret_names, *optional_names) if os.environ.get(name)
)
secret_patterns = set(secret_bytes)
public_access_prefix = b"dianzi-r02-"
for name in (*secret_names, *optional_names):
    if not os.environ.get(name):
        continue
    secret = os.environ[name].encode()
    fragment_source = (
        secret[len(public_access_prefix):]
        if name == "DIANZI_SCAN_MINIO_ACCESS_KEY" and secret.startswith(public_access_prefix)
        else secret
    )
    secret_patterns.update(
        fragment_source[index:index + 8] for index in range(len(fragment_source) - 7)
    )
filenames = subprocess.check_output(["git", "diff", "--cached", "--name-only", "-z"]).split(b"\0")
matched_paths: list[str] = []
checked_paths: list[str] = []
expanded_paths: list[str] = []
for encoded_path in filenames:
    if not encoded_path:
        continue
    filename = encoded_path.decode("utf-8")
    captured = subprocess.run(["git", "show", ":" + filename], capture_output=True, check=True)
    checked_paths.append(filename)
    payloads = [captured.stdout]
    if filename.endswith(".gz"):
        payloads.append(expand_gzip_log(captured.stdout))
        expanded_paths.append(filename)
    if any(secret in blob for blob in payloads for secret in secret_patterns):
        matched_paths.append(filename)
receipt = {
    "started_at": started_at,
    "ended_at": datetime.now(clock).isoformat(timespec="seconds"),
    "source": "git staged blob; authorized secret environment; full bytes and every 8-byte fragment",
    "checked_paths": checked_paths,
    "gzip_expanded_paths": expanded_paths,
    "checked_secret_references": len(secret_bytes),
    "checked_patterns": len(secret_patterns),
    "public_prefix_exclusion": "MinIO access identifier uses documented public prefix; full identifier and random suffix fragments remain checked",
    "matches": len(matched_paths),
    "matched_paths": matched_paths,
}
print(json.dumps(receipt, ensure_ascii=False, indent=2))
raise SystemExit(1 if matched_paths else 0)
