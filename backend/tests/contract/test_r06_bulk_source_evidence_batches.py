"""The source batch contract limits each SQL write and retains every supplied coordinate."""

from contextlib import nullcontext

from tests.integration.test_r06_bulk_source_evidence_pg import source_block
from tests.integration.test_r06_catalog_documents_pg import NOW

from ai_intel.knowledge.revisions import register_source_revision_blocks


class RevisionResult:
    def first(self):
        return ("public", None, True)


class CapturingSession:
    def __init__(self):
        self.writes = []

    def begin_nested(self):
        return nullcontext()

    def execute(self, statement, rows=None):
        if rows is not None:
            self.writes.append((statement.table.name, rows))
        return RevisionResult()


def test_bounded_500_row_writes_keep_501_blocks_and_unclaimed_verified_quotes():
    session = CapturingSession()
    blocks = tuple(source_block(index) for index in range(501))
    ids = register_source_revision_blocks(
        session, "revision", blocks, "public", None, NOW, attach_full_block_evidence=True
    )
    assert len(ids) == len(set(ids)) == 501
    assert [(table, len(rows)) for table, rows in session.writes] == [
        ("text_blocks", 500),
        ("evidence", 500),
        ("text_blocks", 1),
        ("evidence", 1),
    ]
    quotes = [row for table, rows in session.writes if table == "evidence" for row in rows]
    assert [row["block_id"] for row in quotes] == list(ids)
    assert all(row["supports_claim"] is False for row in quotes)
    assert all(row["coordinate_version"] == "fulltext_unicode_v1" for row in quotes)
    assert quotes[-1]["start_offset"] == 500 * len("原文🙂\n")
