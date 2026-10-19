"""Freeze input bytes and compile test-only metadata; never copy business models into src."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import textwrap
from pathlib import Path

from sqlalchemy import Column, MetaData, Table, Text
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import AddConstraint, CreateIndex, CreateTable

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
INPUTS = (
    ("r07", "D:/wt/r07-input-audit", "014de585413c8a82a04d00b1ff2fbd1ff62d733b",
     "reports/runs/recovery_r07_input_audit_20261016/0023_input_audit_proposal.sql"),
    ("r12", "D:/wt/r12-conversation-context", "f557df069a0e0eb74194557ebdb9be338d9a5b0e",
     "backend/src/ai_intel/answering/conversation_models.py"),
    ("r10", "D:/wt/r10-neo4j-projection-fix2", "e8e4086fccc2d9c3f2f582f85e185f5b6f395f0b",
     "backend/src/ai_intel/knowledge/graph_projection_models.py"),
    ("r18", "D:/wt/r18-api-key-credential", "8ae692b5c2824c368b6296481d12695babc717cd",
     "backend/src/ai_intel/api/credential_models.py"),
)


def migration(name: str, parent: str, statements: list[str]) -> None:
    source = (
        f'"""Forward frozen recovery DDL; historical rows retain authority.\n\n'
        f"Revision ID: {name}\nRevises: {parent}\n" + '"""\n\n'
        "from alembic import op\n\n"
        f'revision = "{name}"\ndown_revision = "{parent}"\n'
        "branch_labels = None\ndepends_on = None\n\n\n"
        "def upgrade() -> None:\n"
        '    """Add only the approved fields, sidecars and integrity guards."""\n'
    )
    for statement in statements:
        lines = [line.expandtabs(4).rstrip() for line in statement.strip().splitlines()]
        sql = "\n".join("\n".join(textwrap.wrap(line, width=100, break_long_words=False,
                                               break_on_hyphens=False)) for line in lines)
        source += '    op.execute(\n        """\n' + sql + '\n        """\n    )\n'
    source += (
        "\n\ndef downgrade() -> None:\n"
        '    """Preserve receipts and revocation history; use approved forward repair."""\n'
        '    raise RuntimeError("recovery history requires forward-only recovery")\n'
    )
    (ROOT / "backend/migrations/versions" / (name + ".py")).write_text(
        source, encoding="utf-8", newline="\n"
    )


def main() -> None:
    manifest = []
    compiled: dict[str, list[str]] = {}
    ownership_function = ""
    ownership_triggers: tuple[str, ...] = ()
    for label, directory, revision, path in INPUTS:
        actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=directory, text=True).strip()
        assert actual == revision
        original = (Path(directory) / path).read_bytes()
        frozen = RUN / (label + "_frozen" + Path(path).suffix)
        frozen.write_bytes(original)
        manifest.append({"label": label, "worktree": directory, "revision": revision,
                         "path": path, "sha256_raw": hashlib.sha256(original).hexdigest(),
                         "git_blob": subprocess.check_output(
                             ["git", "rev-parse", f"{revision}:{path}"], cwd=directory, text=True
                         ).strip(), "snapshot": frozen.name})
        if label == "r07":
            assert manifest[-1]["sha256_raw"] == (
                "ee2fde666548f57cdd56376e443d00592ee107a3efb4d6c169e9c1df6581bbd6"
            )
            compiled[label] = original.decode("utf-8").replace("\r\n", "\n").strip().split(";\n\n")
            continue
        parsed = ast.parse(original.decode("utf-8"))
        parsed.body = [node for node in parsed.body if not (
            isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("ai_intel")
        )]
        reference = MetaData()
        Table("users", reference, Column("user_id", Text, primary_key=True))
        Table("grounded_answers", reference, Column("answer_id", Text, primary_key=True))
        namespace: dict[str, object] = {"metadata": reference}
        exec(compile(parsed, str(frozen), "exec"), namespace)
        tables = [table for table in reference.sorted_tables
                  if table.name not in {"users", "grounded_answers"}]
        ddl = [str(CreateTable(table).compile(dialect=postgresql.dialect())).strip()
               for table in tables]
        for table in tables:
            for constraint in sorted(table.foreign_key_constraints,
                                     key=lambda value: value.name or ""):
                if constraint.use_alter:
                    ddl.append(str(AddConstraint(constraint).compile(dialect=postgresql.dialect())))
            for index in sorted(table.indexes, key=lambda value: value.name):
                ddl.append(str(CreateIndex(index).compile(dialect=postgresql.dialect())))
        compiled[label] = ddl
        (RUN / (label + "_metadata.sql")).write_text(
            ";\n\n".join(ddl) + ";\n", encoding="utf-8", newline="\n"
        )
        if label == "r12":
            ownership_function = str(namespace["OWNERSHIP_FUNCTION_DDL"])
            ownership_triggers = tuple(namespace["OWNERSHIP_TRIGGER_DDLS"])
    (RUN / "frozen_inputs.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    migration("0023_enrichment_input_audit", "0022_sbom_sidecars", [
        *compiled["r07"],
        "ALTER FUNCTION guard_enrichment_input_audit() SET search_path FROM CURRENT",
        """CREATE FUNCTION prevent_enrichment_input_audit_deletion() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN
IF OLD.input_audit_payload IS NOT NULL THEN
RAISE EXCEPTION 'input audit receipt is immutable' USING ERRCODE='23514';
END IF;
RETURN OLD;
END $$""",
        """CREATE TRIGGER enrichment_input_audit_delete_guard BEFORE DELETE ON enrichment_job_steps
FOR EACH ROW EXECUTE FUNCTION prevent_enrichment_input_audit_deletion()""",
    ])
    migration("0024_conversation_context", "0023_enrichment_input_audit", [
        *compiled["r12"], ownership_function,
        "ALTER FUNCTION qa_validate_turn_ownership() SET search_path FROM CURRENT",
        *ownership_triggers,
        """CREATE FUNCTION prevent_qa_turn_changes() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'conversation turns are immutable' USING ERRCODE='23514'; END $$""",
        """CREATE TRIGGER qa_conversation_turns_immutable BEFORE UPDATE OR DELETE
ON qa_conversation_turns FOR EACH ROW EXECUTE FUNCTION prevent_qa_turn_changes()""",
    ])
    migration("0025_graph_projection", "0024_conversation_context", [
        *compiled["r10"],
        """ALTER TABLE graph_projection_batches ADD CONSTRAINT ck_graph_projection_payload_sha256
CHECK (payload_sha256 = encode(sha256(payload),'hex'))""",
        """CREATE FUNCTION prevent_graph_projection_batch_changes() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN
RAISE EXCEPTION 'graph projection batches are immutable' USING ERRCODE='23514'; END $$""",
        """CREATE TRIGGER graph_projection_batches_immutable BEFORE UPDATE OR DELETE
ON graph_projection_batches FOR EACH ROW EXECUTE FUNCTION prevent_graph_projection_batch_changes()""",
    ])
    migration("0026_api_key_credentials", "0025_graph_projection", compiled["r18"])
    print(json.dumps({"frozen": len(manifest), "migrations": 4}))


if __name__ == "__main__":
    main()
