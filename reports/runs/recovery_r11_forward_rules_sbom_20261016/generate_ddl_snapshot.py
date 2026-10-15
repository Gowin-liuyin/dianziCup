"""Authoring-only metadata compilation freezes literal PostgreSQL DDL into Alembic files."""

import re
import sys
import textwrap
from pathlib import Path

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from ai_intel.assessment.assessment_persistence import ASSESSMENT_TABLES
from ai_intel.assessment.rule_persistence import APPEND_ONLY_SQL, RULE_LIFECYCLE_SQL, RULE_TABLES
from ai_intel.assets.sbom_persistence_models import (
    SIDECAR_IMMUTABILITY_SQL,
    asset_snapshot_sbom_sidecars,
)

ROOT = Path(__file__).resolve().parents[3]


def write_snapshot(revision, previous, tables, trigger_sql):
    path = ROOT / "backend/migrations/versions" / (revision + ".py")
    assert not path.exists()
    statements = []
    for table in tables:
        ddl = str(CreateTable(table).compile(dialect=postgresql.dialect())).strip()
        statements.append(ddl)
        statements.extend(
            str(CreateIndex(index).compile(dialect=postgresql.dialect()))
            for index in sorted(table.indexes, key=lambda index: index.name)
        )
    statements.extend(statement.strip() for statement in trigger_sql)
    if revision.startswith("0021"):
        statements.extend(
            "CREATE TRIGGER "
            + table.name
            + "_immutable BEFORE UPDATE OR DELETE ON "
            + table.name
            + " FOR EACH ROW EXECUTE FUNCTION r11_require_append_only();"
            for table in tables
            if table.name != "condition_rule_versions"
        )
    source = (
        '"""Add frozen immutable R11 history through the production forward chain.\n\n'
        f"Revision ID: {revision}\nRevises: {previous}\n"
        + '"""\n\n'
        + "from alembic import op\n\n"
        + f'revision = "{revision}"\ndown_revision = "{previous}"\n'
        + "branch_labels = None\ndepends_on = None\n\n\n"
        + "def upgrade() -> None:\n"
        + '    """Create only new tables; existing facts, bytes and hashes are unchanged."""\n'
    )
    for statement in statements:
        statement = "\n".join(
            textwrap.fill(line.strip(), width=92, break_long_words=False, break_on_hyphens=False)
            for line in statement.splitlines()
        )
        source += '    op.execute(\n        """\n' + statement + '\n        """\n    )\n'
    source += (
        "\n\ndef downgrade() -> None:\n" + '    """Preserve evidence history; disable writers '
        'and use an approved forward repair."""\n'
        + '    raise RuntimeError("R11 immutable history cannot be downgraded; '
        'use forward repair")\n'
    )
    path.write_text(source, encoding="utf-8", newline="\n")


def format_existing():
    for name in ("0021_condition_assessments", "0022_sbom_sidecars"):
        path = ROOT / "backend/migrations/versions" / (name + ".py")
        pattern = r'(op.execute\(\n\s*"""\n)(.*?)(\n\s*"""\n\s*\))'

        def replace(match):
            value = "\n".join(
                textwrap.fill(
                    line.strip(), width=92, break_long_words=False, break_on_hyphens=False
                )
                for line in match[2].splitlines()
            )
            return match[1] + value + match[3]

        path.write_text(
            re.sub(pattern, replace, path.read_text(), flags=re.S), encoding="utf-8", newline="\n"
        )


if __name__ == "__main__" and len(sys.argv) > 1:
    assert sys.argv[1] == "--format-existing"
    format_existing()
elif __name__ == "__main__":
    write_snapshot(
        "0021_condition_assessments",
        "0020_hybrid_retrieval",
        (*RULE_TABLES, *ASSESSMENT_TABLES),
        (RULE_LIFECYCLE_SQL, APPEND_ONLY_SQL),
    )
    write_snapshot(
        "0022_sbom_sidecars",
        "0021_condition_assessments",
        (asset_snapshot_sbom_sidecars,),
        (SIDECAR_IMMUTABILITY_SQL,),
    )
