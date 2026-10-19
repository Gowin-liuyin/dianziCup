"""Freeze exact approved strengthening separately from original input proposal bytes."""

import ast
import hashlib
import json
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
records = []
for path in sorted((ROOT / "backend/migrations/versions").glob("002[3456]_*.py")):
    source = path.read_bytes()
    statements = [node.args[0].value.strip() for node in ast.walk(ast.parse(source.decode()))
                  if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                  and node.func.attr == "execute" and isinstance(node.args[0], ast.Constant)]
    for statement in statements:
        if any(token in statement for token in (
            "prevent_qa_turn_changes", "prevent_graph_projection_batch_changes",
            "prevent_enrichment_input_audit_deletion", "SET search_path FROM CURRENT",
            "ck_graph_projection_payload_sha256",
        )):
            records.append({"migration": path.name, "statement": statement,
                            "sha256_utf8": hashlib.sha256(statement.encode()).hexdigest()})
(RUN / "approved_guards.json").write_text(json.dumps(records, indent=2) + "\n",
                                         encoding="utf-8", newline="\n")
print(json.dumps({"guard_statements": len(records)}))
