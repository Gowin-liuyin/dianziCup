"""Check the official driver lock change and commit only its dependency checkpoint."""

import hashlib
import importlib.metadata
import json
import re
import subprocess
import tomllib
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
BASELINE = "3baeb8809d3950a091e8db114be7a28049b74b36"
FILES = ["backend/pyproject.toml", "backend/uv.lock", "docs/decisions/CR-R10_neo4j_driver_dependency.md"]


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def versions(raw):
    return {entry["name"]: entry["version"] for entry in tomllib.loads(raw.decode())["package"]}


started = now()
assert git("rev-parse", "HEAD").decode().strip() == BASELINE
assert not git("diff", "--cached", "--name-only").strip()
user_path = ROOT / "frontend/tsconfig.tsbuildinfo"
user_hash = hashlib.sha256(user_path.read_bytes()).hexdigest()
before = versions(git("show", BASELINE + ":backend/uv.lock"))
after = versions((ROOT / "backend/uv.lock").read_bytes())
changed = {name: [value, after.get(name)] for name, value in before.items() if after.get(name) != value}
added = {name: value for name, value in after.items() if name not in before}
assert changed == {}
assert added == {"neo4j": "6.4.0", "pytz": "2026.5"}
lock = tomllib.loads((ROOT / "backend/uv.lock").read_text(encoding="utf-8"))
driver = next(entry for entry in lock["package"] if entry["name"] == "neo4j")
assert any(wheel["hash"] == "sha256:fdd048ba827be138063b045cf59e40056fbf0405ac02dadc24f64e369fbd9d3d" for wheel in driver["wheels"])
commands = []
sync_started = now()
with (RUN / "neo4j_dependency_sync.log").open("xb") as output:
    sync = subprocess.run(["uv", "sync", "--project", "backend", "--locked"], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=60)
commands.append({"argv": ["uv", "sync", "--project", "backend", "--locked"], "cwd": str(ROOT), "started_at": sync_started, "ended_at": now(), "exit_code": sync.returncode})
assert sync.returncode == 0
assert importlib.metadata.version("neo4j") == "6.4.0"
from neo4j import GraphDatabase

with GraphDatabase.driver("bolt://127.0.0.1:27687", auth=None, telemetry_disabled=True, connection_timeout=3) as offline_driver:
    assert offline_driver is not None
smoke = {"started_at": sync_started, "ended_at": now(), "driver": importlib.metadata.version("neo4j"), "network_calls": 0, "constructed_with_telemetry_disabled": True, "authentication_test": "separate owned-runtime evidence; not this offline smoke", "installed_license_expression": importlib.metadata.metadata("neo4j").get("License-Expression"), "before_packages": len(before), "after_packages": len(after), "added_packages": added, "changed_old_versions": changed}
(RUN / "neo4j_dependency_smoke.json").write_text(json.dumps(smoke, indent=2) + "\n", encoding="utf-8", newline="\n")
document = f"""# CR-R10 · 官方 Neo4j Python driver 锁定

文档首次创建时间：{started}
本次写作开始时间：{started}
本次写作结束时间：{now()}
最后更新时间：{now()}
状态：批准建设目标内的必要依赖 checkpoint；生产投影/整卡/阶段未验收。
主控：/root。基线：{BASELINE}。

R10/R12 已批准图派生索引需要真实 Bolt 事务；复用官方 driver，避免自写 Bolt 协议、连接池、事务或重试框架。固定 neo4j==6.4.0，新增其传递依赖 pytz==2026.5；原 {len(before)} 个包版本未改变，锁文件共 {len(after)} 个包。项目 Python 3.12 在官方支持范围。

官方元数据与 wheel 校验依据：[PyPI 6.4.0](https://pypi.org/project/neo4j/6.4.0/)，wheel SHA256 fdd048ba827be138063b045cf59e40056fbf0405ac02dadc24f64e369fbd9d3d。该版本页面许可证为 Apache-2.0 AND Python-2.0；最终第三方许可证目录必须保留。存在较新 6.4.1 不代表本次已测试版本，不能将其兼容性套用本锁。

修改仅 pyproject.toml/uv.lock 与本变更单，不改公共评分/八对象/原验收。原 approved 基础设施目标不需新的用户审批。R10 投影 adapter 会使用固定参数 Cypher，PG 为事实/权限/任务权威；driver 与测试 server telemetry 均关闭，由 owned-runtime 实测证据核对。不能把 driver 导入成功称为产品图接通。

兼容性：官方 driver 配置保持独立；已有 PG/API/Celery 返回值与认证合同不变。测试 Community5.26.32 已独立 owner 实际认证返回 Bolt5.8；具体运行、安全负例与版本证据仍待新独立 reviewer，本变更单不代签。当前测试 tini TERM 转发因缺KILL失败，exact Docker stop 已发生但 graceful shutdown 未通过，另记 runtime 问题不掩盖。

迁移：本依赖无需数据库 migration。后续 PG 投影表为独立前向0025，由主控所有；不得用 Neo4j 另建事实真相。回滚：先关闭新 graph_apply/default projection wiring，再回退这三个依赖 checkpoint 文件并 uv sync --locked；保留 PG 历史与派生测试卷，不 destructive downgrade、不删 volume。已发布后的依赖撤除需查所有 import 与 worker 配置再审。

验证：本脚本实际执行 uv sync --locked，exit0；离线构造 driver telemetry_disabled=True 不发网络，已记录 smoke JSON。实际 auth/Bolt/transaction 用例在 R10 owned-runtime/作者包中，不合并为 live 来源证据。原 uv add 命令发生在此前工具输出中，其逐秒起止未单独落盘，写历史未记录；不根据mtime推算。本次命令的起止与退出在 neo4j_dependency_commit_receipt.json；新增下载费用 unknown，不写0。

任务与测试影响：R10 真实 projection 与恢复/并发负例；R12 多跳可选派生候选仍须回 PG ACL；R20 资源恢复与租户隔离。初审冻结将核本 CR/锁/hash、原包版本不变、真实资源与负例，不签整个 R10/G-C。没有改变金标、分母、阈值或授权资产。
"""
(ROOT / FILES[2]).write_text(document, encoding="utf-8", newline="\n")
subprocess.run(["git", "diff", "--check", "--", *FILES], cwd=ROOT, capture_output=True, check=True)
subprocess.run(["git", "add", "--", *FILES], cwd=ROOT, capture_output=True, check=True)
assert set(git("diff", "--cached", "--name-only").decode().splitlines()) == set(FILES)
diff = git("diff", "--cached", "--", *FILES)
assert not re.search(rb"sk-[a-zA-Z0-9]{24,}|BEGIN (?:RSA |OPENSSH )?PRIVATE KEY|apikey\s*[:=]\s*['\"]?[a-zA-Z0-9]{24}", diff)
(RUN / "neo4j_dependency_staged_diff.log").write_bytes(diff)
commit_started = now()
with (RUN / "neo4j_dependency_commit.log").open("xb") as output:
    commit = subprocess.run(["git", "commit", "-m", "checkpoint R10 pin official Neo4j driver and preserve existing dependency versions"], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=30)
assert commit.returncode == 0
assert user_hash == hashlib.sha256(user_path.read_bytes()).hexdigest()
receipt = {"started_at": started, "ended_at": now(), "baseline": BASELINE, "commit_sha": git("rev-parse", "HEAD").decode().strip(), "selected_files": FILES, "before_packages": len(before), "after_packages": len(after), "changed_old_versions": changed, "added_packages": added, "commands": commands, "commit_started_at": commit_started, "commit_exit_code": commit.returncode, "user_buildinfo_unchanged": True, "user_buildinfo_sha256": user_hash, "stage_accepted": False, "push": "not_run", "fee": "unknown"}
(RUN / "neo4j_dependency_commit_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(receipt))
