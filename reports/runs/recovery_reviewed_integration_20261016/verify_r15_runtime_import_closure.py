"""核验R15固定源的内部导入闭包，补齐根集成遗漏的已冻合同。"""

import ast
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
SOURCE = "a4e3bd94d3af66a19e1fde94b0100d3faf3c3ba9"
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
path = "backend/src/ai_intel/api/recommendation_contracts.py"
target = ROOT / path
assert not target.exists()
frozen = subprocess.check_output(["git", "show", SOURCE + ":" + path], cwd=ROOT)
target.write_bytes(frozen)
paths = [target, ROOT / "backend/src/ai_intel/api/recommendation_routes.py"]
paths.extend((ROOT / "backend/src/ai_intel/recommendations").glob("*.py"))
imports = set()
for source_path in paths:
    for node in ast.walk(ast.parse(source_path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("ai_intel"):
            imports.add(node.module)
        elif isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names if alias.name.startswith("ai_intel"))
missing = []
for module in sorted(imports):
    module_path = ROOT / "backend/src" / module.replace(".", "/")
    if not module_path.with_suffix(".py").exists() and not (module_path / "__init__.py").exists():
        missing.append(module)
receipt = {"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "source_sha": SOURCE, "restored_path": path, "sha256": hashlib.sha256(frozen).hexdigest(), "checked_files": len(paths), "internal_import_count": len(imports), "missing_imports": missing, "original_run": "r15_default_mount.xml: 5 collection errors before business assertions", "scope": "static internal imports plus missing frozen module; not integration acceptance"}
(RUN / "r15_runtime_import_closure.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt, ensure_ascii=True))
assert not missing
