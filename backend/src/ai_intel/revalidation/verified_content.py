"""One attempt carries verified immutable bytes; PostgreSQL still owns every business input."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal

from ai_intel.api.actor_references import ActorReference
from ai_intel.infrastructure.content_store import SHA256_PATTERN, ContentStorage, StoredContent
from ai_intel.infrastructure.minio_store import ObjectStoreUnavailableError
from ai_intel.workers.executor import JobExecutionResult

MAX_VERIFIED_CONTENT_BYTES = 64 * 1024 * 1024
MAX_SINGLE_VERIFIED_SOURCE_BYTES = 2 * 1024 * 1024
MAX_VERIFIED_SOURCE_READS = 100 * 20
PROOF_MODE = "current_attempt_verified_bytes"


class VerificationBudgetExceeded(ValueError):
    """A stopped verification is incomplete work, never a negative risk conclusion."""


class VerifiedContentInvalid(ValueError):
    """Fixed diagnostics keep unavailable proof distinct from any default successful content."""


def checked_source_bytes(content_hash: str, content: bytes) -> bytes:
    if (
        not isinstance(content_hash, str)
        or not SHA256_PATTERN.fullmatch(content_hash)
        or type(content) is not bytes
        or len(content) > MAX_SINGLE_VERIFIED_SOURCE_BYTES
        or hashlib.sha256(content).hexdigest() != content_hash
    ):
        raise VerifiedContentInvalid("revalidation_verified_source_invalid")
    return content


class VerifiedContentRecorder:
    """Real storage is reopened for every public read; only deduplicated bytes form the proof."""

    def __init__(self, store: ContentStorage, declared_sizes: Mapping[str, int]) -> None:
        self._store = store
        self._declared_sizes = MappingProxyType(dict(declared_sizes))
        self._content: dict[str, bytes] = {}
        self._total_bytes = 0
        self._reads = 0

    def read_verified(self, content_hash: str) -> bytes:
        size = self._declared_sizes.get(content_hash)
        if (
            size is None
            or type(size) is not int
            or size < 0
            or size > MAX_SINGLE_VERIFIED_SOURCE_BYTES
        ):
            raise VerifiedContentInvalid("revalidation_verified_source_size_unavailable")
        if self._reads == MAX_VERIFIED_SOURCE_READS:
            raise VerificationBudgetExceeded("revalidation_verification_budget_exhausted")
        if (
            content_hash not in self._content
            and self._total_bytes + size > MAX_VERIFIED_CONTENT_BYTES
        ):
            raise VerificationBudgetExceeded("revalidation_verification_budget_exhausted")
        self._reads += 1
        try:
            source_bytes = self._store.read_verified(content_hash)
        except ValueError as error:
            raise VerifiedContentInvalid("revalidation_verified_source_invalid") from error
        except (OSError, ObjectStoreUnavailableError) as error:
            raise VerifiedContentInvalid("revalidation_verified_source_unavailable") from error
        content = checked_source_bytes(content_hash, source_bytes)
        if len(content) != size:
            raise VerifiedContentInvalid("revalidation_verified_source_size_changed")
        if content_hash not in self._content:
            self._content[content_hash] = content
            self._total_bytes += len(content)
        return content

    def freeze(self) -> Mapping[str, bytes]:
        return MappingProxyType(dict(self._content))

    def store_bytes(self, payload: bytes) -> StoredContent:
        raise PermissionError("verified source proof is read only")

    def delete_object(self, content_hash: str) -> None:
        raise PermissionError("verified source proof is read only")


@dataclass(frozen=True)
class VerifiedSourceProof:
    job_id: str
    worker_id: str
    attempt_count: int
    tenant_id: str
    actor: ActorReference = field(repr=False)
    request_sha256: str
    content_by_hash: Mapping[str, bytes] = field(repr=False)
    mode: Literal["current_attempt_verified_bytes"] = "current_attempt_verified_bytes"

    def __post_init__(self) -> None:
        if self.mode != PROOF_MODE or not SHA256_PATTERN.fullmatch(self.request_sha256):
            raise VerifiedContentInvalid("revalidation_verified_proof_invalid")
        content = dict(self.content_by_hash)
        for content_hash, source_bytes in content.items():
            checked_source_bytes(content_hash, source_bytes)
        if (
            len(content) > MAX_VERIFIED_SOURCE_READS
            or sum(len(source_bytes) for source_bytes in content.values())
            > MAX_VERIFIED_CONTENT_BYTES
        ):
            raise VerificationBudgetExceeded("revalidation_verification_budget_exhausted")
        object.__setattr__(self, "content_by_hash", MappingProxyType(content))


@dataclass(frozen=True, kw_only=True)
class VerifiedFanInResult(JobExecutionResult):
    proof: VerifiedSourceProof = field(repr=False)


class FrozenVerifiedContent:
    """No external fallback exists; a new hash requires a new real verification attempt."""

    def __init__(self, proof: VerifiedSourceProof) -> None:
        self._content = proof.content_by_hash

    def read_verified(self, content_hash: str) -> bytes:
        source_bytes = self._content.get(content_hash)
        if source_bytes is None:
            raise VerifiedContentInvalid("revalidation_verified_source_unavailable")
        return checked_source_bytes(content_hash, source_bytes)

    def store_bytes(self, payload: bytes) -> StoredContent:
        raise PermissionError("verified source proof is read only")

    def delete_object(self, content_hash: str) -> None:
        raise PermissionError("verified source proof is read only")
