"""A full commit reference must contain hexadecimal SHA characters."""

import pytest

from ai_intel.ingestion.sources.repository import RepositoryFetchError, normalize_repository_record


@pytest.mark.parametrize("identifier", ["z" * 40, "a" * 39 + " ", "\0" * 40, "main"])
def test_non_hex_or_floating_commit_rejected(identifier: str) -> None:
    with pytest.raises(RepositoryFetchError):
        normalize_repository_record(
            {
                "record_type": "commit",
                "fixed_identifier": identifier,
                "title": "Commit",
                "related_product": "ollama",
            }
        )


def test_full_hex_sha_preserved_without_floating_ref_resolution() -> None:
    sha = "0123456789abcdef" * 2 + "01234567"
    record = normalize_repository_record(
        {
            "record_type": "commit",
            "fixed_identifier": sha,
            "title": "Commit",
            "related_product": "ollama",
        }
    )
    assert record.fixed_identifier == sha
