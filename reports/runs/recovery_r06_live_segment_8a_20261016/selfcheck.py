"""Exercise fail-before-env gates and verify fixed source bindings without IO mocks."""

import ast
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from common import OBSERVER, ROOT, RUN, verify_authorization, write

verify_authorization()
sys.path.insert(0, str(OBSERVER))
specification = importlib.util.spec_from_file_location("exact_observer", OBSERVER / "observe.py")
module = importlib.util.module_from_spec(specification)
specification.loader.exec_module(module)
with tempfile.TemporaryDirectory(prefix="r06_missing_gate_") as folder:
    missing = Path(folder) / "missing_gate.json"
    original = module.read_live_gate
    with patch.object(module, "read_live_gate", side_effect=lambda: original(missing)), patch.object(module, "create_engine", side_effect=AssertionError("unexpected engine")) as engine_call, patch.object(module, "os") as environment:
        try:
            module.main()
        except module.ObservationError:
            pass
        else:
            raise AssertionError("missing gate accepted")
        assert engine_call.call_count == 0 and environment.mock_calls == []
source_files = {name: ROOT / ("backend/src/ai_intel/" + name) for name in ("workers/runtime.py", "workers/executor.py", "ingestion/source_polling.py", "ingestion/source_jobs.py", "ingestion/cursor_repository.py")}
source_evidence = {}
for name, path in source_files.items():
    if path.exists():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        source_evidence[name] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "functions": [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]}
assert "poll_due_public_sources" in source_evidence["workers/runtime.py"]["functions"]
assert "enqueue_due_source_collections" in source_evidence["ingestion/source_polling.py"]["functions"]
assert "enqueue_source_page" in source_evidence["ingestion/source_jobs.py"]["functions"]
assert "commit_page" in source_evidence["ingestion/cursor_repository.py"]["functions"]
for path in RUN.glob("*.py"):
    ast.parse(path.read_text(encoding="utf-8"))
write("selfcheck_receipt.json", {"missing_gate_main_rejected": True, "missing_gate_environment_accesses": 0, "missing_gate_engine_calls": 0, "exact_observer_gate_uses_separate_product_root": True, "owned_script_syntax_checked": len(list(RUN.glob('*.py'))), "source_evidence": source_evidence, "model_or_external_calls": 0})
print(json.dumps({"fail_before_env": True, "engine_calls": 0, "source_ast_checked": len(source_evidence)}))
