"""Disable one approved setting and restart the same owned CID before its old deadline."""

import hashlib
import json
import os
import re
import shutil
import signal
import time
from datetime import datetime
from pathlib import Path

import runtime

resource = json.loads((runtime.OWNED / "resource.json").read_text())
assert (
    resource["container_id"]
    == "c0d49f69954c9d7b5d3ab0420347b99d96e9fdbeaf87ece3032b8c3430cd41ab"
)
assert resource["deadline"] == "2026-10-16T19:35:43.312788+08:00"
assert runtime.now() < datetime.fromisoformat(resource["deadline"])
container = runtime.inspect_container(resource["container_id"])
runtime.assert_owned_container(container, resource)
assert container["state"]["Running"]
assert Path(resource["volume_mountpoint"]).stat().st_ino == 701675
assert runtime.process_identity(resource["supervisor"]["pid"]) == resource["supervisor"]
archive = runtime.OUTPUT / "usage_reporting_before"
archive.mkdir()
for name in (
    "resource_started.json",
    "snapshot.json",
    "bolt_smoke.json",
    "kernel_security.json",
    "windows_health.json",
    "launch_resume.json",
    "container_startup.redacted.log",
    "logs_and_secret_scan.json",
):
    shutil.copy2(runtime.OUTPUT / name, archive / name)
before_path = runtime.OWNED / "neo4j.before_usage_disabled.conf"
after_path = runtime.OWNED / "neo4j.usage_disabled.conf"
assert not before_path.exists() and not after_path.exists()
runtime.docker(
    [
        "cp",
        resource["container_id"] + ":/var/lib/neo4j/conf/neo4j.conf",
        str(before_path),
    ],
    label="usage_conf_read_owned",
)
before_path.chmod(0o600)
original = before_path.read_bytes()
source = original.decode()
pattern = re.compile(r"^\s*dbms\.usage_report\.enabled\s*=.*$", re.MULTILINE)
active_lines = pattern.findall(source)
assert len(active_lines) <= 1, "Conflicting original usage-report settings"
if active_lines:
    assert active_lines[0].split("=", 1)[1].strip() in ("true", "false")
    changed = pattern.sub("dbms.usage_report.enabled=false", source)
else:
    changed = source.rstrip("\n") + "\ndbms.usage_report.enabled=false\n"
assert pattern.findall(changed) == ["dbms.usage_report.enabled=false"]
after_path.write_text(changed)
after_path.chmod(0o644)
receipt = {
    "prepared_at": runtime.now().isoformat(),
    "container_id": resource["container_id"],
    "deadline": resource["deadline"],
    "setting": "dbms.usage_report.enabled",
    "old_effective_value": "true",
    "new_value": "false",
    "active_original_line_count": len(active_lines),
    "original_config_sha256": hashlib.sha256(original).hexdigest(),
    "modified_config_sha256": hashlib.sha256(after_path.read_bytes()).hexdigest(),
    "original_config_private_path": str(before_path),
    "modified_config_private_path": str(after_path),
    "old_supervisor": resource["supervisor"],
    "old_guardian": resource["guardian"],
    "wrapper_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
}
runtime.write_json(runtime.OUTPUT / "usage_reporting_transition.json", receipt)
runtime.docker(
    [
        "cp",
        str(after_path),
        resource["container_id"] + ":/var/lib/neo4j/conf/neo4j.conf",
    ],
    label="usage_conf_write_owned",
)
runtime.docker(
    [
        "exec",
        "--user",
        "7474:7474",
        resource["container_id"],
        "neo4j-admin",
        "server",
        "validate-config",
    ],
    timeout=25,
    label="usage_validate_config",
)
receipt["configuration_validation"] = "passed"
receipt["stop_requested_at"] = runtime.now().isoformat()
runtime.write_json(runtime.OUTPUT / "usage_reporting_transition.json", receipt)
os.kill(resource["supervisor"]["pid"], signal.SIGTERM)
wait_until = time.monotonic() + 35
while True:
    assert time.monotonic() < wait_until, "Owned previous generation did not end"
    container = runtime.inspect_container(resource["container_id"])
    runtime.assert_owned_container(container, resource)
    alive = False
    for name in ("supervisor", "guardian"):
        try:
            current = runtime.process_identity(resource[name]["pid"])
        except (FileNotFoundError, ProcessLookupError):
            continue
        if current == resource[name]:
            alive = True
    if not alive and not container["state"]["Running"]:
        break
    time.sleep(1)
receipt["stopped_at_observed"] = runtime.now().isoformat()
receipt["stopped_state"] = container["state"]
for name in ("heartbeat.json", "termination.json"):
    path = runtime.OWNED / name
    assert path.resolve() == path and path.parent == runtime.OWNED
    content = path.read_bytes()
    (archive / ("owned_" + name)).write_bytes(content)
    runtime.write_json(
        archive / (name + ".hash.json"),
        {
            "sha256": hashlib.sha256(content).hexdigest(),
            "byte_length": len(content),
            "path": str(path),
        },
    )
    path.rename(runtime.OWNED / (name + ".usage_before"))
resource["supervisor"] = runtime.process_identity(os.getpid())
resource.pop("guardian")
resource.pop("container_process")
resource.pop("started_at")
resource["usage_reporting_disabled_config_sha256"] = receipt["modified_config_sha256"]
resource["supervisor_wrapper_sha256"] = receipt["wrapper_sha256"]
resource["supervisor_wrapper_path"] = str(Path(__file__).resolve())
resource["usage_reporting_restart_prepared_at"] = runtime.now().isoformat()
runtime.write_json(runtime.OWNED / "resource.json", resource)
runtime.write_json(runtime.OUTPUT / "usage_reporting_transition.json", receipt)
runtime.run_supervision(resource)
