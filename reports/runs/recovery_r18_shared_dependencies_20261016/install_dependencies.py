"""Resolve approved protocol dependencies under the root-owned lock without paid IO."""

import importlib.metadata
import json
import os
import subprocess
import tomllib
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
BASELINE = "5b29b3e8c6ea1d10ca50cf2d2006f8460b53253c"


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def versions(raw):
    return {item["name"]: item["version"] for item in tomllib.loads(raw.decode())["package"]}


assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == BASELINE
assert not subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT).strip()
assert not subprocess.check_output(["git", "status", "--porcelain", "--", "backend/pyproject.toml", "backend/uv.lock"], cwd=ROOT).strip()
before = versions((ROOT / "backend/uv.lock").read_bytes())
commands = []
child_environment = os.environ.copy()
for name in ("UV_EXTRA_INDEX_URL", "UV_INDEX_USERNAME", "UV_INDEX_PASSWORD"):
    child_environment.pop(name, None)
child_environment["UV_HTTP_TIMEOUT"] = "30"
child_environment["UV_HTTP_RETRIES"] = "2"
steps = (
    ("protocol_add", ["uv", "add", "--project", "backend", "--no-sync", "--index-url", "https://pypi.org/simple", "mcp==2.3.0", "tiktoken==0.14.0"]),
    ("schema_stubs_add", ["uv", "add", "--project", "backend", "--dev", "--no-sync", "--index-url", "https://pypi.org/simple", "types-jsonschema==4.26.0.20261006"]),
    ("semantic_and_protocol_sync", ["uv", "sync", "--project", "backend", "--locked", "--extra", "semantic"]),
)
started = now()
for name, argv in steps:
    item = {"name": name, "argv": argv, "cwd": str(ROOT), "started_at": now()}
    with (RUN / (name + ".log")).open("xb") as output:
        result = subprocess.run(argv, cwd=ROOT, env=child_environment, stdout=output, stderr=subprocess.STDOUT, timeout=180)
    item.update({"ended_at": now(), "exit_code": result.returncode})
    commands.append(item)
    (RUN / "commands.json").write_text(json.dumps(commands, indent=2) + "\n", encoding="utf-8", newline="\n")
    assert result.returncode == 0, "dependency operation failed; preserve log without retries"
after = versions((ROOT / "backend/uv.lock").read_bytes())
changed = {name: [value, after.get(name)] for name, value in before.items() if after.get(name) != value}
added = {name: value for name, value in after.items() if name not in before}
for name, version in (("mcp", "2.3.0"), ("tiktoken", "0.14.0"), ("types-jsonschema", "4.26.0.20261006"), ("onnxruntime", "1.24.4"), ("tokenizers", "0.22.2"), ("numpy", "2.4.2"), ("neo4j", "6.4.0")):
    assert importlib.metadata.version(name) == version
from mcp.server import MCPServer
import numpy
import onnxruntime
import tiktoken
import tokenizers

server = MCPServer("dianzi-dependency-offline-smoke")
assert server is not None and numpy.__version__ == "2.4.2"
assert onnxruntime.__version__ == "1.24.4" and tokenizers.__version__ == "0.22.2"
assert tiktoken.__version__ == "0.14.0"
receipt = {"started_at": started, "ended_at": now(), "baseline": BASELINE, "before_packages": len(before), "after_packages": len(after), "changed_old_versions": changed, "added_packages": added, "commands": commands, "smoke": "official MCPServer and semantic runtime imports only; no model/encoding/server initialization", "paid_model_or_provider_calls": 0, "package_network_calls": "unknown", "fees": "unknown", "stage_accepted": False, "push": "not_run"}
(RUN / "dependency_install_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
assert not changed, "review existing version changes before root commits the lock"
print(json.dumps(receipt))
