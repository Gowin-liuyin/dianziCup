"""Bulk source blocks reject every malformed row before database access."""

import hashlib
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from ai_intel.knowledge.revisions import (
    QuoteConsistencyError,
    SourceRevisionBlock,
    register_source_revision_blocks,
)


def block(ordinal=0):
    text = "来源🙂"
    return SourceRevisionBlock(
        ordinal,
        0,
        len(text),
        text,
        hashlib.sha256(text.encode()).hexdigest(),
        "json_field",
        None,
        "/title",
    )


class NoDatabaseAccess:
    def __getattr__(self, name):
        raise AssertionError(f"unexpected database access: {name}")


@pytest.mark.parametrize(
    "blocks",
    [
        (replace(block(), end_offset=2),),
        (replace(block(), text_sha256="0" * 64),),
        (replace(block(), ordinal=-1),),
        (replace(block(), page_number=0),),
        (replace(block(), text="\x00"),),
        (block(), block()),
    ],
)
def test_invalid_rows_fail_before_io(blocks):
    with pytest.raises(QuoteConsistencyError):
        register_source_revision_blocks(
            NoDatabaseAccess(),
            "revision",
            blocks,
            "public",
            None,
            datetime(2026, 10, 16, tzinfo=UTC),
            attach_full_block_evidence=True,
        )
