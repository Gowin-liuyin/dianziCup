"""有界构建官方固定MinIO安全版本，不更改系统工具链或现有服务。"""

import hashlib
import json
import os
import signal
import subprocess
import tarfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path("/tmp/dianzi-minio-r02-20261015")
ARCHIVE = Path("/mnt/c/Users/yinha/.codex/cache/dianzi/minio-r02-20261015/go1.27.2.linux-amd64.tar.gz")
EXPECTED_SHA256 = "ecbadb99091a3f46e31f5f934b068b1864eafa7995211b39eaddf76996045fe5"
CGROUP = Path("/sys/fs/cgroup/dianzi-r01-20261014/minio-build-20261015")
SOURCE = "github.com/minio/minio@RELEASE.2025-10-15T17-29-55Z"
RUN = Path("/mnt/d/dianzi/reports/runs/recovery_r02_minio_20261015")


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def enter_build_group() -> None:
    """只把本次child放进自己的子组，不移动其他进程。"""
    (CGROUP / "cgroup.procs").write_text(str(os.getpid()))


def main() -> int:
    started = now()
    if hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() != EXPECTED_SHA256:
        raise ValueError("portable compiler checksum mismatch")
    ROOT.mkdir(mode=0o700, exist_ok=True)
    toolchain = ROOT / "toolchain"
    if toolchain.exists():
        raise FileExistsError("build area already initialized; inspect before retry")
    toolchain.mkdir(mode=0o700)
    with tarfile.open(ARCHIVE) as archive:
        for member in archive.getmembers():
            resolved = (toolchain / member.name).resolve()
            if not resolved.is_relative_to(toolchain.resolve()) or member.issym() or member.islnk():
                raise ValueError("unexpected archive path/link")
        archive.extractall(toolchain)
    if not CGROUP.parent.exists() or CGROUP.exists():
        raise ValueError("project resource parent missing or build group already exists")
    CGROUP.mkdir()
    for name, value in {"memory.max": "1073741824", "memory.swap.max": "0",
                        "pids.max": "256", "cpu.max": "100000 100000"}.items():
        (CGROUP / name).write_text(value)
    environment = dict(os.environ)
    environment.update(GOBIN=str(ROOT / "bin"), GOCACHE=str(ROOT / "buildcache"),
                       GOMODCACHE=str(ROOT / "modcache"), GOMAXPROCS="2", GOMEMLIMIT="512MiB",
                       GOFLAGS="-p=1", CGO_ENABLED="0", GOTOOLCHAIN="local")
    compiler = str(toolchain / "go/bin/go")
    version = subprocess.check_output([compiler, "version"], env=environment, text=True).strip()
    command = [compiler, "install", SOURCE]
    with (RUN / "minio_build.log").open("xb") as output:
        child = subprocess.Popen(command, env=environment, cwd=ROOT,
                                 stdout=output, stderr=subprocess.STDOUT,
                                 start_new_session=True, preexec_fn=enter_build_group)
        (RUN / "minio_build_start.json").write_text(json.dumps({
            "started_at": started, "pid": child.pid, "command": command, "compiler": version,
            "cgroup": str(CGROUP), "max_seconds": 1200, "memory_bytes": 1073741824,
            "cpu_cores": 1, "pids_limit": 256, "sum_verification": "Go default enabled",
        }, indent=2))
        try:
            exit_code = child.wait(timeout=1200)
            timed_out = False
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=10)
            exit_code = 124
            timed_out = True
    binary = ROOT / "bin/minio"
    receipt = {"started_at": started, "ended_at": now(), "exit_code": exit_code,
               "timed_out": timed_out, "source": SOURCE, "compiler": version,
               "binary_exists": binary.exists(), "cgroup_events": (CGROUP / "memory.events").read_text()}
    if exit_code == 0:
        receipt["binary_sha256"] = hashlib.sha256(binary.read_bytes()).hexdigest()
        (RUN / "minio_build_modules.log").write_bytes(subprocess.check_output([compiler, "version", "-m", str(binary)]))
    (RUN / "minio_build_end.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
