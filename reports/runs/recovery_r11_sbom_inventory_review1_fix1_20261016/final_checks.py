"""最终源码检查及有资格名的本机图追踪；业务/测试原件只读。"""

import json

from review_runner_final import PYTHON, ROOT, RUN, command


def main():
    changed = [
        "src/ai_intel/assets/inventory.py", "src/ai_intel/assets/sbom_inventory.py",
        "src/ai_intel/assets/sbom_inventory_contracts.py",
        "tests/unit/test_r11_sbom_inventory_uri_privacy.py", "tests/unit/test_r11_sbom_inventory_uri_privacy_followup.py",
        "tests/integration/test_r11_sbom_inventory_uri_privacy.py", "tests/integration/test_r11_sbom_inventory_uri_privacy_followup.py",
    ]
    assert command("mypy_final", [str(PYTHON), "-m", "mypy", "src"]) == 0
    assert command("ruff_final", [str(PYTHON), "-m", "ruff", "check", *changed]) == 0
    assert command("format_final", [str(PYTHON), "-m", "ruff", "format", "--check", *changed]) == 0
    assert command("callers_final_rg", ["rg", "-n", "safe_sbom_snapshot|safe_sbom_sidecar|freeze_sbom_sidecar|get_snapshot\\(|get_snapshot_sbom\\(|list_assets\\(|list_snapshots\\(|import_manifest\\(|read_asset\\(", "backend/src/ai_intel/assets"], cwd=ROOT) == 0
    project = "r11-sbom-review1-fix1-final-assets-20261016"
    prefix = ["wsl.exe", "-e", "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json"]
    receipts = []
    for function in ("get_snapshot", "read_asset", "list_assets", "list_snapshots", "get_snapshot_sbom", "import_manifest", "safe_sbom_sidecar", "safe_sbom_snapshot"):
        module = "sbom_inventory" if function.startswith("safe_") else "inventory.InventoryService"
        qualified = project + "." + module + "." + function
        name = "cbm_qualified_final_" + function
        assert command(name, [*prefix, "trace_path", json.dumps({"project": project, "function_name": qualified, "direction": "both", "depth": 3})], cwd=ROOT) == 0
        lines = (RUN / (name + ".log")).read_text().splitlines()
        response = json.loads(next(line for line in reversed(lines) if line.startswith("{")))
        assert not response.get("isError")
        text = "\n".join(item.get("text", "") for item in response.get("content", []))
        assert "callees_total:" in text and "callers_total:" in text and "function:" in text
        receipts.append({"function": qualified, "parsed": True, "is_error": False, "log": name + ".log"})
    (RUN / "cbm_qualified_final_parsed.json").write_bytes(json.dumps(receipts, indent=2).encode())


if __name__ == "__main__":
    main()
