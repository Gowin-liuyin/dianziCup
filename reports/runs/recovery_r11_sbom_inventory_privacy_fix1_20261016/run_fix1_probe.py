"""独审冻结probe逐字节副本，显式加载原共享hook；仅绑定独占资源，不改输入断言。"""

import ast
import importlib.util
import sys
from urllib.parse import unquote

import pytest
from run_checks import ROOT, RUN


def main():
    probe = RUN / "test_fix1_probes.py"
    shared_spec = importlib.util.spec_from_file_location(
        "shared_review_redaction", ROOT / "backend/tests/conftest.py"
    )
    shared = importlib.util.module_from_spec(shared_spec)
    shared_spec.loader.exec_module(shared)
    resource_spec = importlib.util.spec_from_file_location(
        "review_sbom_resource", RUN / "fix1_resources/test_r11_sbom_inventory_postgres.py"
    )
    resource = importlib.util.module_from_spec(resource_spec)
    sys.modules["review_sbom_resource"] = resource
    resource_spec.loader.exec_module(resource)
    literals = {"synthetic_password", "synthetic-password"}
    for node in ast.walk(ast.parse(probe.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value
            if len(value) >= 8 and ("://" in value or "synthetic_password" in value):
                literals.update((value, unquote(value)))
    original = shared.redact_test_connection_output

    def redact(output, dynamic_credentials=()):
        protected = original(output, dynamic_credentials)
        for value in sorted(literals, key=len, reverse=True):
            protected = protected.replace(value, "[redacted review value]")
        return protected

    shared.redact_test_connection_output = redact
    return pytest.main([str(probe), *sys.argv[1:]], plugins=[shared])


if __name__ == "__main__":
    raise SystemExit(main())
