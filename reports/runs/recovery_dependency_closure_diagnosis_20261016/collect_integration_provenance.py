"""Record scoped integration provenance and existing receipts without rerunning suites."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import xml.etree.ElementTree as element_tree
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path("D:/dianzi")
AUTHOR = Path("D:/wt/r18-sdk-canonical-verification-integration")
RUN = ROOT / "reports/runs/recovery_dependency_closure_diagnosis_20261016"
ROOT_RUN = ROOT / "reports/runs/recovery_reviewed_integration_20261016"
SOURCE = "02ce8d6b8072253c26a5df1a49e1b574f2668498"
MATERIAL = "3db7b6cdf33ab1dc5d6c8801a54603b20137ada7"
FROZEN_ROOT = "d68b9c653aa8eced6eeb75b6d293617c6cce5094"


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def git_blob(directory: Path, revision: str, relative: str) -> dict[str, object]:
    result = subprocess.run(
        ["git", "show", f"{revision}:{relative}"], cwd=directory, capture_output=True, check=False
    )
    if result.returncode:
        return {"exists": False, "read_exit_code": result.returncode}
    content = result.stdout
    blob = hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()
    return {"exists": True, "git_blob": blob, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content), "read_exit_code": 0}


def main() -> None:
    started = now()
    inputs = [
        "backend/tests/contract/test_r18_public_extensions.py",
        "contracts/schemas/public_api_extensions_v1.json",
    ]
    rows = []
    for relative in inputs:
        content = (ROOT / relative).read_bytes()
        canonical = content.replace(b"\r\n", b"\n")
        row = {
            "path": relative, "category": "existing_contract_and_test_for_root_372_not_canonical_358",
            "source": git_blob(AUTHOR, SOURCE, relative),
            "material": git_blob(AUTHOR, MATERIAL, relative),
            "root_frozen": git_blob(ROOT, FROZEN_ROOT, relative),
            "root_raw_bytes": len(content), "root_raw_sha256": hashlib.sha256(content).hexdigest(),
            "root_canonical_lf_sha256": hashlib.sha256(canonical).hexdigest(),
        }
        rows.append(row)
    public_extension = json.loads((ROOT / inputs[1]).read_bytes())
    legacy = json.loads((ROOT / "contracts/schemas/public_api_v2.json").read_bytes())
    preserved = all(public_extension["$defs"][name] == definition for name, definition in legacy["$defs"].items())
    sdk = json.loads((RUN / "sdk_dependency_closure.json").read_text(encoding="utf-8"))
    local_imports = []
    for item in sdk["imports"]:
        name = item.get("module")
        relative = None
        if name == "ai_intel_client":
            relative = "sdk/python/ai_intel_client/__init__.py"
        elif isinstance(name, str) and name.startswith("ai_intel_client."):
            relative = "sdk/python/" + name.replace(".", "/") + ".py"
        elif name in {"r18_test_paths", "test_independent_native", "test_independent_boundaries", "test_models"}:
            relative = "sdk/python/tests/" + name + ".py"
        if relative is not None:
            local_imports.append({"consumer": item["path"], "line": item["line"], "module": name, "target": relative, "root_exists": (ROOT / relative).is_file()})
    diagnostics = []
    for name in ["integrate_reviewed_source_sdk_batch5.py", "verify_r15_runtime_import_closure.py"]:
        path = ROOT_RUN / name
        raw = path.read_bytes()
        tree = ast.parse(raw)
        selectors = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                value = node.value
                if value in {"diff-tree", "--name-only", "--no-commit-id", "backend/", "sdk/python/tests/", "ai_intel.", "ai_intel_client", "r18_test_paths"}:
                    selectors.append({"line": node.lineno, "value": value})
        diagnostics.append({"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw), "raw_sha256": hashlib.sha256(raw).hexdigest(), "selection_literals": selectors})
    receipts = []
    for name in ["source_batch5", "source_batch5_fix1", "sdk_batch5", "sdk_canonical_batch5", "sdk_canonical_358"]:
        path = ROOT_RUN / (name + ".json")
        if not path.is_file():
            receipts.append({"name": name, "exists": False})
            continue
        raw = path.read_bytes()
        receipt = json.loads(raw)
        xml = ROOT_RUN / (name + ".xml")
        cases = element_tree.parse(xml).findall(".//testcase") if xml.is_file() else []
        failures = sum(case.find("failure") is not None for case in cases)
        errors = sum(case.find("error") is not None for case in cases)
        skipped = sum(case.find("skipped") is not None for case in cases)
        names = {(case.attrib.get("classname"), case.attrib.get("name")) for case in cases}
        receipts.append({"name": name, "exists": True, "path": path.relative_to(ROOT).as_posix(), "raw_sha256": hashlib.sha256(raw).hexdigest(), "original_receipt": receipt, "xml_counts": {"total": len(cases), "distinct": len(names), "failed": failures, "errors": errors, "skipped": skipped, "passed": len(cases)-failures-errors-skipped}})
    result = {
        "started_at": started, "finished_at": now(), "exit_code": 0,
        "supplemental_root_372_inputs": rows, "legacy_definitions_preserved": preserved,
        "local_import_edges": local_imports, "missing_local_imports": [item for item in local_imports if not item["root_exists"]],
        "root_importer_evidence": diagnostics, "existing_root_test_receipts": receipts,
        "executed_test_count": 0, "network_requests": 0, "pg_requests": 0, "model_requests": 0,
    }
    (RUN / "integration_provenance.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"started_at": started, "finished_at": result["finished_at"], "missing_local_imports": len(result["missing_local_imports"]), "legacy_definitions_preserved": preserved, "existing_receipts": [{"name": item["name"], "exists": item["exists"], "xml_counts": item.get("xml_counts")} for item in receipts]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
