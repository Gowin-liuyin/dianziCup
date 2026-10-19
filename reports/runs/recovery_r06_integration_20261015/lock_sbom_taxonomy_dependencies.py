"""Pin required SBOM and taxonomy parsers while retaining unrelated locked versions."""

import hashlib
import json
import subprocess
import tomllib
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def run_command(name, argv):
    started = now()
    with (RUN / (name + ".log")).open("xb") as output:
        result = subprocess.run(argv, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=150)
    record = {"started_at": started, "ended_at": now(), "cwd": str(ROOT), "argv": argv, "exit_code": result.returncode}
    (RUN / (name + ".json")).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    if result.returncode:
        raise SystemExit(result.returncode)
    return record


started = now()
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
before_bytes = subprocess.check_output(["git", "show", head + ":backend/uv.lock"], cwd=ROOT)
before = tomllib.loads(before_bytes.decode())
commands = []
commands.append(run_command("taxonomy_dependency_add", ["uv", "add", "--project", "backend", "PyYAML==6.0.3", "--no-sync", "--index-url", "https://pypi.org/simple"]))
commands.append(run_command("taxonomy_stub_add", ["uv", "add", "--project", "backend", "--dev", "types-PyYAML==6.0.12.20260906", "--no-sync", "--index-url", "https://pypi.org/simple"]))
after_bytes = (ROOT / "backend/uv.lock").read_bytes()
after = tomllib.loads(after_bytes.decode())
old = {p["name"]: p["version"] for p in before["package"]}
new = {p["name"]: p["version"] for p in after["package"]}
changed = {name: [version, new.get(name)] for name, version in old.items() if new.get(name) != version}
assert changed == {}, changed
assert {name: version for name, version in new.items() if name not in old} == {"packageurl-python": "0.17.6", "types-pyyaml": "6.0.12.20260906"}
commands.append(run_command("sbom_taxonomy_dependency_sync", ["uv", "sync", "--project", "backend", "--frozen", "--all-extras", "--index-url", "https://pypi.org/simple"]))
smoke = "from importlib.metadata import version; from packageurl import PackageURL; import yaml; assert PackageURL.from_string('pkg:pypi/numpy@2.0.0').version == '2.0.0'; assert yaml.safe_load('catalogue: atlas') == {'catalogue':'atlas'}; assert version('PyYAML') == '6.0.3'; assert version('packageurl-python') == '0.17.6'; assert version('types-PyYAML') == '6.0.12.20260906'; print('purl, safe YAML and typing package smoke passed')"
commands.append(run_command("sbom_taxonomy_dependency_smoke", [str(ROOT / "backend/.venv/Scripts/python.exe"), "-c", smoke]))
ended = now()
receipt = {"started_at": started, "ended_at": ended, "baseline_head": head, "before_packages": len(old), "after_packages": len(new), "changed_old_versions": changed, "added_packages": {name: version for name, version in new.items() if name not in old}, "lock_sha256": hashlib.sha256(after_bytes).hexdigest(), "commands": commands, "business_tests": "not_run; dependency-only smoke", "product_and_paid_wire_calls": 0, "package_download_cost": "unknown"}
(RUN / "sbom_taxonomy_dependency_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
cr = f"""# CR-R11/R07 · SBOM 与分类目录必要依赖

首次创建时间：{ended}
写作开始/结束时间：{started} / {ended}
主控：/root
状态：awaiting_review；不代表任务或阶段验收

目标与依据：用户已批准真实 SBOM、九维富化和成熟依赖。复用 Package URL 官方 Python 实现解析 purl，复用 PyYAML SafeLoader 读取 MITRE ATLAS 的固定版本 YAML；不实现自制编码或 YAML 解析器。类型 stub 用于严格 mypy 检查，不全局忽略第三方类型。

变更：生产直接依赖 packageurl-python==0.17.6（原未安装）、PyYAML==6.0.3（原为 semantic 间接依赖，现提升直接）；开发直接依赖 types-PyYAML==6.0.12.20260906。本次锁文件原 {len(old)} 包版本全部保留，仅新增上述 purl 与 stub，现 {len(new)} 包。仅修改 backend/pyproject.toml、backend/uv.lock，业务调用方由各任务独立实现和审查。

兼容：Python 3.12；原环境配置、数据库 schema、API、指标分母和金标无改变。基础生产安装可读 YAML，不再依赖 semantic extra 恰巧安装它。Package URL 与 YAML 使用输入大小、深度、重复键和类型边界由相应业务模块负责。

迁移：uv sync --project backend --frozen --all-extras；生产按现有部署方式安装冻结依赖，不执行数据库迁移、不下载新模型。现有 PyYAML 版本没有升级。

回滚：只回退本变更的 manifest/lock 并按旧 lock sync；在 SBOM/taxonomy 调用方集成后，需连同依赖该库的调用方回退，不能留下导入失败入口。无业务数据删除。

任务影响：R11/T24 SBOM adapter 与 R07 分类目录输入需要本依赖；不减少任何验收范围。尚未接线的模块和高密度组件容量缺口不因此通过。

验证：四条命令 exit 0，真实 purl/SafeLoader/安装版本 smoke 通过；业务测试未运行。本机最初 purl add/sync 已执行但未记录完整起止，历史未记录；本次记录从 {started} 起算，不补写旧时间。详见 reports/runs/recovery_r06_integration_20261015/sbom_taxonomy_dependency_receipt.json。

官方依据：[Package URL 0.17.6](https://pypi.org/project/packageurl-python/0.17.6/)、[PyYAML 6.0.3](https://pypi.org/project/PyYAML/6.0.3/)、[types-PyYAML](https://pypi.org/project/types-PyYAML/)（6.0.* 类型）。包下载费用 unknown，无产品模型或测绘调用。待各切片的新独立 reviewer 核对实际调用与边界。
"""
(ROOT / "docs/decisions/CR-R11_R07_parser_dependencies.md").write_text(cr, encoding="utf-8", newline="\n")
print(json.dumps({"before_packages": len(old), "after_packages": len(new), "unchanged_old_versions": not changed, "receipt": "sbom_taxonomy_dependency_receipt.json"}))
