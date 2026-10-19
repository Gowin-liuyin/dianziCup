"""Offline official tokenizer loading and the complete MCP result budget."""

from __future__ import annotations

import hashlib
from importlib import import_module
from importlib.metadata import version
from pathlib import Path
from types import FunctionType

import tiktoken
from mcp_types import CallToolResult
from tiktoken.load import load_tiktoken_bpe

OUTPUT_BUDGET_PROFILE = "r18-output-budget-1"
MAX_TOOL_OUTPUT_TOKENS = 8000
MAX_TOOL_OUTPUT_BYTES = 1048576
ENCODING_URL = "https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken"
ENCODING_SHA256 = "446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d"
ENCODING_SIZE_BYTES = 3613922


class OutputBudgetConfigurationError(ValueError):
    """The pinned tokenizer could not be loaded without network access."""


class OutputBudgetTokenizationError(RuntimeError):
    """The native tokenizer failed; no count or complete output is claimed."""


def load_offline_encoding(cache_file: Path) -> tiktoken.Encoding:
    """Reuse the official constructor and parser with a private in-memory reader.

    Neither official module globals nor environment/cache settings are patched.
    The verified bytes remain the sole input even if the file later changes.
    """
    if version("tiktoken") != "0.14.0":
        raise OutputBudgetConfigurationError("not_configured")
    try:
        with cache_file.open("rb") as cache:
            verified_bytes = cache.read(ENCODING_SIZE_BYTES + 1)
    except OSError:
        raise OutputBudgetConfigurationError("not_configured") from None
    if (
        len(verified_bytes) != ENCODING_SIZE_BYTES
        or hashlib.sha256(verified_bytes).hexdigest() != ENCODING_SHA256
    ):
        raise OutputBudgetConfigurationError("not_configured")

    def read_verified_bytes(path: str, expected_hash: str | None = None) -> bytes:
        if path != ENCODING_URL or expected_hash != ENCODING_SHA256:
            raise OutputBudgetConfigurationError("not_configured")
        return verified_bytes

    local_parser = FunctionType(
        load_tiktoken_bpe.__code__,
        {**load_tiktoken_bpe.__globals__, "read_file_cached": read_verified_bytes},
    )
    official_constructor: object = import_module("tiktoken_ext.openai_public").o200k_base
    if not isinstance(official_constructor, FunctionType):
        raise OutputBudgetConfigurationError("not_configured")
    local_constructor = FunctionType(
        official_constructor.__code__,
        {**official_constructor.__globals__, "load_tiktoken_bpe": local_parser},
    )
    configuration: object = local_constructor()
    if not isinstance(configuration, dict):
        raise OutputBudgetConfigurationError("not_configured")
    name = configuration.get("name")
    pattern = configuration.get("pat_str")
    raw_ranks = configuration.get("mergeable_ranks")
    raw_special = configuration.get("special_tokens")
    if name != "o200k_base" or not isinstance(pattern, str):
        raise OutputBudgetConfigurationError("not_configured")
    if not isinstance(raw_ranks, dict) or not isinstance(raw_special, dict):
        raise OutputBudgetConfigurationError("not_configured")
    ranks: dict[bytes, int] = {}
    special: dict[str, int] = {}
    for token, rank in raw_ranks.items():
        if not isinstance(token, bytes) or type(rank) is not int:
            raise OutputBudgetConfigurationError("not_configured")
        ranks[token] = rank
    for token, rank in raw_special.items():
        if not isinstance(token, str) or type(rank) is not int:
            raise OutputBudgetConfigurationError("not_configured")
        special[token] = rank
    return tiktoken.Encoding(
        name="o200k_base", pat_str=pattern, mergeable_ranks=ranks, special_tokens=special
    )


class McpOutputBudget:
    """Count the final compact JSON, including text, structured data and metadata."""

    def __init__(self, cache_file: Path) -> None:
        self.encoding = load_offline_encoding(cache_file)
        self.profile = OUTPUT_BUDGET_PROFILE

    @classmethod
    def for_fixture(cls, encoding: tiktoken.Encoding) -> McpOutputBudget:
        """Explicit isolated test counting; this never advertises the formal profile."""
        budget = cls.__new__(cls)
        budget.encoding = encoding
        budget.profile = "explicit-fixture-token-budget"
        return budget

    def fits(self, result: CallToolResult) -> bool:
        serialized = result.model_dump_json(by_alias=True, exclude_none=True)
        if len(serialized.encode("utf-8")) > MAX_TOOL_OUTPUT_BYTES:
            return False
        try:
            return len(self.encoding.encode_ordinary(serialized)) <= MAX_TOOL_OUTPUT_TOKENS
        except BaseException as error:
            if (
                type(error).__module__ == "pyo3_runtime"
                and type(error).__name__ == "PanicException"
            ):
                raise OutputBudgetTokenizationError("tokenizer_unavailable") from None
            raise
