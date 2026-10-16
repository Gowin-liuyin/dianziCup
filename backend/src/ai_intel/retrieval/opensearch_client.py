"""Small fixed-index REST adapter; caller supplies the trusted HTTP client and credentials."""

from __future__ import annotations

import asyncio
import json
import math
import re
import time
from collections.abc import Callable
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, RootModel, ValidationError

from ai_intel.domain.access import AccessScope
from ai_intel.retrieval.hybrid import BRANCH_LIMIT, authorized_scope_keys, candidate_values
from ai_intel.retrieval.hybrid_contracts import (
    CorpusCandidate,
    HybridQuery,
    HybridRetrievalError,
    IndexGeneration,
)


class Shards(BaseModel):
    model_config = ConfigDict(strict=True)
    failed: int = Field(ge=0)


class SearchHit(BaseModel):
    model_config = ConfigDict(strict=True, populate_by_name=True)
    chunk_id: str = Field(alias="_id", min_length=1, max_length=128)
    score: float = Field(alias="_score", allow_inf_nan=False)


class SearchHits(BaseModel):
    hits: list[SearchHit]


class SearchResponse(BaseModel):
    model_config = ConfigDict(strict=True, populate_by_name=True)
    timed_out: bool
    shards: Shards = Field(alias="_shards")
    hits: SearchHits


class BulkAction(BaseModel):
    model_config = ConfigDict(strict=True)
    status: int


class BulkItem(BaseModel):
    index: BulkAction


class BulkResponse(BaseModel):
    model_config = ConfigDict(strict=True)
    errors: bool
    items: list[BulkItem]


class DeleteResponse(BaseModel):
    model_config = ConfigDict(strict=True)
    timed_out: bool
    failures: list[object]


class RefreshResponse(BaseModel):
    model_config = ConfigDict(strict=True, populate_by_name=True)
    shards: Shards = Field(alias="_shards")


class IndexSpaceMetadata(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    generation_id: str
    model_version: str
    dimension: int


class IndexMappings(BaseModel):
    model_config = ConfigDict(strict=True, populate_by_name=True)
    metadata: IndexSpaceMetadata = Field(alias="_meta")
    dynamic: str


class IndexDefinition(BaseModel):
    mappings: IndexMappings


class MappingResponse(RootModel[dict[str, IndexDefinition]]):
    pass


def bm25_body(
    generation: IndexGeneration, scope: AccessScope, query: HybridQuery
) -> dict[str, object]:
    allowed: list[dict[str, object]] = [
        {
            "bool": {
                "filter": [
                    {"term": {"visibility": "public"}},
                    {"bool": {"must_not": {"exists": {"field": "tenant_id"}}}},
                ]
            }
        }
    ]
    keys = authorized_scope_keys(scope)
    if len(keys) > 1:
        allowed.append(
            {
                "bool": {
                    "filter": [
                        {"term": {"visibility": "tenant"}},
                        {"term": {"tenant_id": scope.tenant_id}},
                    ]
                }
            }
        )
    time_bounds = {"lte": query.available_before.isoformat()}
    if query.available_after is not None:
        time_bounds["gte"] = query.available_after.isoformat()
    return {
        "size": BRANCH_LIMIT,
        "_source": False,
        "timeout": "5s",
        "sort": [{"_score": "desc"}, {"chunk_id": "asc"}],
        "query": {
            "bool": {
                "must": [{"match": {"chunk_text": {"query": query.text}}}],
                "filter": [
                    {"term": {"generation_id": generation.generation_id}},
                    {"term": {"model_version": generation.model_version}},
                    {"terms": {"scope_key": list(keys)}},
                    {"bool": {"should": allowed, "minimum_should_match": 1}},
                    {"range": {"available_at": time_bounds}},
                ],
            }
        },
    }


class OpenSearchCorpusClient:
    """No arbitrary URL, raw query, shell, or SQL entry point is exposed to callers."""

    def __init__(
        self,
        client: httpx.Client,
        *,
        deadline: float | None = None,
        async_client_factory: Callable[[], httpx.AsyncClient] | None = None,
    ) -> None:
        parsed = urlsplit(str(client.base_url))
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
            or (
                parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            )
        ):
            raise ValueError("trusted OpenSearch base URL required; remote connections require TLS")
        self.client = client

        def bounded_timeout(value: float | None) -> float:
            return 10.0 if value is None else min(value, 10.0)

        self.request_timeout = httpx.Timeout(
            connect=bounded_timeout(client.timeout.connect),
            read=bounded_timeout(client.timeout.read),
            write=bounded_timeout(client.timeout.write),
            pool=bounded_timeout(client.timeout.pool),
        )
        if (deadline is None) != (async_client_factory is None):
            raise ValueError("a deadline requires an owned asynchronous client factory")
        if deadline is not None and (
            type(deadline) not in (int, float) or not math.isfinite(deadline)
        ):
            raise ValueError("deadline must be a finite monotonic timestamp")
        self.deadline = deadline
        self.async_client_factory = async_client_factory

    @staticmethod
    def _index(generation: IndexGeneration) -> str:
        generation.require_fixed_space()
        if re.fullmatch(r"dianzi_[a-z0-9][a-z0-9_-]{1,180}", generation.index_name) is None:
            raise ValueError("invalid dedicated corpus index name")
        return generation.index_name

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
        content: bytes | None = None,
    ) -> httpx.Response:
        try:
            if self.deadline is not None:
                return asyncio.run(self._request_before_deadline(method, path, body, content))
            response = self.client.request(
                method,
                path,
                json=body,
                content=content,
                headers={"Content-Type": "application/x-ndjson"} if content is not None else None,
                timeout=self.request_timeout,
                follow_redirects=False,
            )
            response.raise_for_status()
            if len(response.content) > 2 * 1024**2:
                raise HybridRetrievalError("opensearch_response_limit")
            return response
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            if status in {401, 403}:
                raise HybridRetrievalError("opensearch_permission_denied") from None
            raise HybridRetrievalError(f"opensearch_http_{status}") from None
        except (httpx.TimeoutException, TimeoutError):
            raise HybridRetrievalError("opensearch_timeout") from None
        except (httpx.HTTPError, ValueError):
            raise HybridRetrievalError("opensearch_unavailable") from None

    async def _request_before_deadline(
        self, method: str, path: str, body: dict[str, object] | None, content: bytes | None
    ) -> httpx.Response:
        """Native async cancellation covers connect, headers, the whole body and client close."""
        if self.deadline is None or self.async_client_factory is None:
            raise HybridRetrievalError("opensearch_deadline_not_configured")
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise HybridRetrievalError("corpus_projection_deadline_exceeded")
        async with asyncio.timeout(remaining):
            async with self.async_client_factory() as client:
                if client.base_url != self.client.base_url:
                    raise HybridRetrievalError("opensearch_origin_mismatch")
                async with client.stream(
                    method,
                    path,
                    json=body,
                    content=content,
                    headers={"Content-Type": "application/x-ndjson"}
                    if content is not None
                    else None,
                    follow_redirects=False,
                ) as response:
                    response.raise_for_status()
                    collected = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(collected) + len(chunk) > 2 * 1024**2:
                            raise HybridRetrievalError("opensearch_response_limit")
                        collected.extend(chunk)
                    return httpx.Response(
                        response.status_code,
                        content=bytes(collected),
                        headers={"Content-Type": response.headers.get("content-type", "")},
                        request=response.request,
                    )

    def create_index(self, generation: IndexGeneration) -> None:
        keyword_fields = (
            "generation_id",
            "chunk_id",
            "evidence_id",
            "revision_id",
            "document_id",
            "source_id",
            "event_id",
            "claim_id",
            "scope_key",
            "visibility",
            "tenant_id",
            "model_version",
            "text_sha256",
            "source_uri",
            "locator",
        )
        properties = {field: {"type": "keyword"} for field in keyword_fields}
        properties.update({"chunk_text": {"type": "text", "analyzer": "cjk"}})
        properties.update(
            {field: {"type": "long"} for field in ("indexed_epoch", "start_offset", "end_offset")}
        )
        properties.update({"available_at": {"type": "date"}})
        body: dict[str, object] = {
            "settings": {"number_of_shards": 1, "number_of_replicas": 0},
            "mappings": {
                "dynamic": "strict",
                "_meta": {
                    "generation_id": generation.generation_id,
                    "model_version": generation.model_version,
                    "dimension": generation.dimension,
                },
                "properties": properties,
            },
        }
        try:
            self._request("PUT", "/" + self._index(generation), body=body)
        except HybridRetrievalError:
            self.verify_index(generation)

    def verify_index(self, generation: IndexGeneration) -> None:
        response = self._request("GET", f"/{self._index(generation)}/_mapping")
        try:
            result = MappingResponse.model_validate_json(response.content)
        except ValidationError:
            raise HybridRetrievalError("opensearch_index_space_invalid") from None
        definition = result.root.get(generation.index_name)
        expected = IndexSpaceMetadata(
            generation_id=generation.generation_id,
            model_version=generation.model_version,
            dimension=generation.dimension,
        )
        if (
            len(result.root) != 1
            or definition is None
            or (definition.mappings.metadata != expected or definition.mappings.dynamic != "strict")
        ):
            raise HybridRetrievalError("index_space_rebuild_required")

    def search(
        self, generation: IndexGeneration, scope: AccessScope, query: HybridQuery
    ) -> tuple[str, ...]:
        response = self._request(
            "POST",
            "/" + self._index(generation) + "/_search",
            body=bm25_body(generation, scope, query),
        )
        try:
            result = SearchResponse.model_validate_json(response.content)
        except ValidationError:
            raise HybridRetrievalError("opensearch_search_contract_invalid") from None
        if result.timed_out or result.shards.failed or len(result.hits.hits) > BRANCH_LIMIT:
            raise HybridRetrievalError("opensearch_search_incomplete")
        identifiers = tuple(hit.chunk_id for hit in result.hits.hits)
        if len(set(identifiers)) != len(identifiers):
            raise HybridRetrievalError("opensearch_search_contract_invalid")
        return identifiers

    def upsert(
        self, generation: IndexGeneration, candidates: tuple[CorpusCandidate, ...], epoch: int
    ) -> None:
        index = self._index(generation)
        for start in range(0, len(candidates), 64):
            batch = candidates[start : start + 64]
            lines: list[str] = []
            for candidate in batch:
                lines.append(json.dumps({"index": {"_id": candidate.chunk_id}}))
                values = candidate_values(candidate)
                values["available_at"] = candidate.available_at.isoformat()
                values.update(
                    {
                        "generation_id": generation.generation_id,
                        "model_version": generation.model_version,
                        "indexed_epoch": epoch,
                    }
                )
                lines.append(json.dumps(values, ensure_ascii=False))
            response = self._request(
                "POST", f"/{index}/_bulk", content=("\n".join(lines) + "\n").encode()
            )
            try:
                result = BulkResponse.model_validate_json(response.content)
            except ValidationError:
                raise HybridRetrievalError("opensearch_bulk_contract_invalid") from None
            if (
                result.errors
                or len(result.items) != len(batch)
                or any(item.index.status not in {200, 201} for item in result.items)
            ):
                raise HybridRetrievalError("opensearch_bulk_incomplete")

    def remove_older_scope(self, generation: IndexGeneration, scope_key: str, epoch: int) -> None:
        response = self._request(
            "POST",
            f"/{self._index(generation)}/_delete_by_query",
            body={
                "query": {
                    "bool": {
                        "filter": [
                            {"term": {"generation_id": generation.generation_id}},
                            {"term": {"scope_key": scope_key}},
                            {"range": {"indexed_epoch": {"lt": epoch}}},
                        ]
                    }
                },
            },
        )
        try:
            result = DeleteResponse.model_validate_json(response.content)
        except ValidationError:
            raise HybridRetrievalError("opensearch_delete_contract_invalid") from None
        if result.timed_out or result.failures:
            raise HybridRetrievalError("opensearch_delete_incomplete")

    def refresh(self, generation: IndexGeneration) -> None:
        response = self._request("POST", f"/{self._index(generation)}/_refresh")
        try:
            result = RefreshResponse.model_validate_json(response.content)
        except ValidationError:
            raise HybridRetrievalError("opensearch_refresh_contract_invalid") from None
        if result.shards.failed:
            raise HybridRetrievalError("opensearch_refresh_incomplete")
