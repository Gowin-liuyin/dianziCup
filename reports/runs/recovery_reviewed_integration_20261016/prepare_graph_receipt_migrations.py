"""从明确冻结的表声明生成前向迁移，不执行工作流或读取任何凭据。"""

import ast
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import sqlalchemy
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from ai_intel.knowledge.models import metadata

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
STARTED = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def load_table_declarations(path: Path, names: set[str]) -> dict[str, object]:
    """只读取表/固定SQL声明，阻止导入作者正在实施的IO与服务。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    selected = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in names for target in node.targets
        ):
            selected.append(node)
    assert len(selected) == len(names)
    namespace = {
        name: getattr(sqlalchemy, name)
        for name in (
            "Table", "Column", "Text", "DateTime", "Integer", "ForeignKey",
            "ForeignKeyConstraint", "CheckConstraint", "UniqueConstraint", "Index",
        )
    }
    namespace.update(metadata=metadata, JSONB=postgresql.JSONB)
    declarations = ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[]))
    exec(compile(declarations, str(path), "exec"), namespace)
    return {name: namespace[name] for name in names}


def create_migration(revision: str, previous: str, statements: list[str]) -> Path:
    target = ROOT / "backend/migrations/versions" / f"{revision}.py"
    if target.exists():
        raise FileExistsError(target)
    source = (
        '"""Install approved persistent records without changing historical tables."""\n\n'
        "from alembic import op\n\n"
        f'revision = "{revision}"\n'
        f'down_revision = "{previous}"\n'
        "branch_labels = None\ndepends_on = None\n\n\n"
        "def upgrade() -> None:\n"
        '    """Create immutable bindings and their explicitly permitted completion transitions."""\n'
    )
    for statement in statements:
        source += '    op.execute(\n        """\n'
        source += "\n".join(line.rstrip() for line in statement.strip().splitlines())
        source += '\n        """\n    )\n'
    source += (
        "\n\ndef downgrade() -> None:\n"
        '    """Retain audit/history; recovery uses separately reviewed forward repairs."""\n'
        f'    raise RuntimeError("{revision} requires forward-only recovery")\n'
    )
    target.write_text(source, encoding="utf-8", newline="\n")
    return target


def table_statements(tables: list[sqlalchemy.Table]) -> list[str]:
    result = []
    for table in tables:
        result.append(str(CreateTable(table).compile(dialect=postgresql.dialect())).strip())
        result.extend(
            str(CreateIndex(index).compile(dialect=postgresql.dialect()))
            for index in sorted(table.indexes, key=lambda item: item.name)
        )
    return result


graph_source = Path(
    "D:/wt/r14-langgraph-workflow/backend/src/ai_intel/investigation/workflow_service.py"
)
graph = load_table_declarations(
    graph_source,
    {"investigation_workflows", "investigation_operations", "WORKFLOW_IMMUTABILITY_SQL"},
)
graph_statements = table_statements(
    [graph["investigation_workflows"], graph["investigation_operations"]]
)
graph_statements.append(graph["WORKFLOW_IMMUTABILITY_SQL"])
graph_target = create_migration(
    "0028_investigation_workflows", "0027_recommendation_history", graph_statements
)

receipt_source = Path(
    "D:/wt/r15-http-mutation-receipts/backend/src/ai_intel/recommendations/mutation_receipts.py"
)
receipt = load_table_declarations(receipt_source, {"recommendation_mutation_receipts"})
receipt_table = receipt["recommendation_mutation_receipts"]
receipt_statements = table_statements([receipt_table])
receipt_statements.extend([
    """CREATE FUNCTION protect_recommendation_mutation_receipt() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN
RAISE EXCEPTION 'recommendation request receipt is immutable' USING ERRCODE='23514';
END $$""",
    """CREATE TRIGGER recommendation_mutation_receipts_immutable
BEFORE UPDATE OR DELETE ON recommendation_mutation_receipts
FOR EACH ROW EXECUTE FUNCTION protect_recommendation_mutation_receipt()""",
])
receipt_target = create_migration(
    "0029_recommendation_receipts", "0028_investigation_workflows", receipt_statements
)
result = {
    "started_at": STARTED,
    "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    "sources": {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (graph_source, receipt_source)
    },
    "generated": {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (graph_target, receipt_target)
    },
    "graph_statements": len(graph_statements),
    "receipt_statements": len(receipt_statements),
    "receipt_columns": [column.name for column in receipt_table.columns],
    "pg_executed": False,
    "status": "awaiting_review",
}
(RUN / "graph_receipt_migration_preparation.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(result, ensure_ascii=True))
