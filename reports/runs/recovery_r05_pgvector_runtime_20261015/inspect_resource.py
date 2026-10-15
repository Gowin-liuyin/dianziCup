"""Record public container limits, actual image digest, and official Python package metadata."""

import importlib.metadata
import json
import subprocess
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ZONE = ZoneInfo("Asia/Shanghai")
DOCKER = [
    "wsl",
    "-d",
    "Ubuntu-22.04",
    "-u",
    "root",
    "--",
    "/tmp/dianzi-docker-static-r01-20261014/portable/docker/docker",
    "--config",
    "/tmp/dianzi-docker-static-r01-20261014/runtime/client-config",
    "-H",
    "unix:///tmp/dianzi-docker-static-r01-20261014/runtime/docker.sock",
]


def now() -> str:
    return datetime.now(ZONE).isoformat(timespec="seconds")


def main() -> None:
    result = {"started_at": now(), "cwd": str(Path.cwd()), "commands": []}
    commands = [
        [
            *DOCKER,
            "inspect",
            "dianzi-test-r01_20261014-postgres",
            "--format",
            "{{.Image}} {{.HostConfig.CgroupParent}} {{.HostConfig.Memory}} "
            "{{.HostConfig.NanoCpus}} {{.HostConfig.PidsLimit}} "
            "{{.HostConfig.NetworkMode}} {{.HostConfig.RestartPolicy.Name}}",
        ],
        [
            *DOCKER,
            "image",
            "inspect",
            "pgvector/pgvector:0.8.2-pg16",
            "--format",
            "{{json .RepoDigests}} {{.Id}} {{.Size}}",
        ],
        [
            "wsl",
            "-d",
            "Ubuntu-22.04",
            "-u",
            "root",
            "--",
            "python3",
            "-c",
            "from pathlib import Path; import json; "
            "root=Path('/sys/fs/cgroup/dianzi-r01-20261014'); "
            "names=['memory.current','memory.max','memory.swap.max',"
            "'cpu.max','pids.current','pids.max']; "
            "print(json.dumps({name: (root/name).read_text().strip() for name in names}))",
        ],
        [
            "wsl",
            "-d",
            "Ubuntu-22.04",
            "-u",
            "root",
            "--",
            "stat",
            "-c",
            "%a %U %n",
            "/tmp/dianzi-docker-static-r01-20261014/runtime/r05-pgvector/connection.json",
        ],
    ]
    for command in commands:
        entry = {"argv": command, "started_at": now()}
        completed = subprocess.run(command, capture_output=True, text=True, timeout=30)
        entry.update(
            ended_at=now(),
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        result["commands"].append(entry)
        assert completed.returncode == 0
        assert not completed.stderr, "resource command emitted an error; review recorded stderr"
    with urllib.request.urlopen("https://pypi.org/pypi/pgvector/json", timeout=20) as response:
        package = json.load(response)
    result["package_recommendation"] = {
        "source": "https://pypi.org/pypi/pgvector/json",
        "version": package["info"]["version"],
        "requires_python": package["info"]["requires_python"],
        "requires_dist": package["info"]["requires_dist"],
        "artifacts": [
            {
                "filename": item["filename"],
                "sha256": item["digests"]["sha256"],
                "size": item["size"],
                "upload_time": item["upload_time_iso_8601"],
            }
            for item in package["urls"]
        ],
        "installed_here": False,
        "official_integration": "https://github.com/pgvector/pgvector-python#sqlalchemy",
        "existing_runtime_versions": {
            name: importlib.metadata.version(name) for name in ("sqlalchemy", "psycopg")
        },
    }
    result.update(ended_at=now(), exit_code=0)
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    (RUN / "resource_inventory.json").write_text(output, encoding="utf-8")
    print(output, end="")


if __name__ == "__main__":
    main()
