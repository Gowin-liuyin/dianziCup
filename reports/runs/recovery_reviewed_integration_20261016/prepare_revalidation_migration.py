"""仅从固定Git表声明生成前向身份绑定迁移，保留原迁移与事实。"""

import ast
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import sqlalchemy
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from ai_intel.knowledge.models import metadata

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
ZONE = ZoneInfo("Asia/Shanghai")
SOURCE_SHA = "e711b3919d36a75fe3bfc3ea6187b5e08d12b204"
SOURCE_PATH = "backend/src/ai_intel/revalidation/persistence_models.py"
started = datetime.now(ZONE).isoformat(timespec="seconds")
frozen = subprocess.check_output(["git", "show", SOURCE_SHA + ":" + SOURCE_PATH], cwd=ROOT)
assert hashlib.sha256(frozen).hexdigest() == "e05e83a5cabf3a0830425bd6bf5ef0ba777dd1fc906fe87a25c6b752d0a842b2"
tree = ast.parse(frozen)
selected = [node for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "revalidation_job_bindings" for target in node.targets)]
assert len(selected) == 1
namespace = {name: getattr(sqlalchemy, name) for name in ("Table", "Column", "Text", "DateTime", "ForeignKey", "CheckConstraint")}
namespace.update(metadata=metadata, JSONB=postgresql.JSONB)
exec(compile(ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[])), SOURCE_PATH, "exec"), namespace)
table = namespace["revalidation_job_bindings"]
assert len(table.columns) == 7
ddl = str(CreateTable(table).compile(dialect=postgresql.dialect())).strip()
target = ROOT / "backend/migrations/versions/0030_revalidation_actor_bindings.py"
if target.exists():
    raise FileExistsError(target)
statements = [ddl, """CREATE FUNCTION protect_revalidation_actor_binding() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN
RAISE EXCEPTION 'revalidation actor binding is immutable' USING ERRCODE='23514';
END $$""", """CREATE TRIGGER revalidation_job_bindings_immutable
BEFORE UPDATE OR DELETE ON revalidation_job_bindings
FOR EACH ROW EXECUTE FUNCTION protect_revalidation_actor_binding()"""]
source = '''"""Install append-only actor bindings; existing PG jobs remain authoritative."""

from alembic import op

revision = "0030_revalidation_actor_bindings"
down_revision = "0029_recommendation_receipts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add immutable server authentication bindings without changing historical rows."""
'''
for statement in statements:
    source += '    op.execute(\n        """\n' + statement + '\n        """\n    )\n'
source += '''

def downgrade() -> None:
    """Retain identities and history; recovery requires a reviewed forward migration."""
    raise RuntimeError("0030_revalidation_actor_bindings requires forward-only recovery")
'''
target.write_text(source, encoding="utf-8", newline="\n")
ended = datetime.now(ZONE).isoformat(timespec="seconds")
receipt = {"started_at": started, "ended_at": ended, "source_sha": SOURCE_SHA, "source_path": SOURCE_PATH, "source_sha256": hashlib.sha256(frozen).hexdigest(), "generated_path": str(target.relative_to(ROOT)), "generated_sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "column_names": [column.name for column in table.columns], "statement_count": len(statements), "pg_executed": False, "status": "awaiting_review"}
(RUN / "revalidation_migration_preparation.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt, ensure_ascii=True))
