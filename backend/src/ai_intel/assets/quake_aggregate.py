"""Quake fixed app searches retain only the official search pagination total."""

from __future__ import annotations

import json
from datetime import datetime
from types import MappingProxyType
from typing import Literal

from pydantic import SecretStr

from ai_intel.assets.aggregate_observations import (
    AggregateGateway,
    AggregateIdentity,
    AggregateObservation,
    AggregateQueryId,
    build_aggregate_gateway,
    decode_aggregate_response,
    network_error_code,
    require_query_id,
    response_error,
    retrieval_time,
    total_result,
)
from ai_intel.infrastructure.network import NetworkPolicyViolation, NetworkRequestError

QUAKE_QUERIES = MappingProxyType({"ollama": 'app:"Ollama"', "vllm": 'app:"vLLM"'})
QUAKE_ENDPOINT = "https://quake.360.net/api/v3/search/quake_service"


class QuakeAggregateConnector:
    """One POST without retries, redirects or support for raw body/URL/query arguments."""

    def __init__(
        self,
        api_key: SecretStr | None = None,
        *,
        fixture_gateway: AggregateGateway | None = None,
        dns_resolver: Literal["system", "cloudflare_doh"] = "system",
    ) -> None:
        if fixture_gateway is not None and api_key is not None:
            raise ValueError("fixture mode cannot receive provider credentials")
        self._data_mode: Literal["live", "fixture"] = (
            "fixture" if fixture_gateway is not None else "live"
        )
        self._gateway: AggregateGateway | None = fixture_gateway
        if fixture_gateway is None and api_key is not None:
            self._gateway = build_aggregate_gateway("quake", api_key, dns_resolver)

    def collect(
        self, query_id: AggregateQueryId, *, retrieved_at: datetime | None = None
    ) -> AggregateObservation:
        require_query_id(query_id)
        if retrieved_at is not None and self._data_mode != "fixture":
            raise ValueError("retrieved_at override requires explicit fixture mode")
        completed_at = retrieval_time(retrieved_at)
        fields: AggregateIdentity = {
            "provider": "quake",
            "query_id": query_id,
            "retrieved_at": completed_at,
            "data_mode": self._data_mode,
        }
        if self._gateway is None:
            return AggregateObservation(
                **fields, outcome="not_configured", error_code="credential_missing"
            )
        request_body = json.dumps(
            {"query": QUAKE_QUERIES[query_id], "start": 0, "size": 1}, separators=(",", ":")
        ).encode("utf-8")
        try:
            response = self._gateway.post_json(QUAKE_ENDPOINT, request_body)
        except (NetworkRequestError, NetworkPolicyViolation) as error:
            return AggregateObservation(
                **fields, outcome="failed", error_code=network_error_code(error)
            )
        completed_at = retrieval_time(retrieved_at)
        fields["retrieved_at"] = completed_at
        http_error = response_error(response)
        if http_error is not None:
            return AggregateObservation(**fields, outcome=http_error[0], error_code=http_error[1])
        try:
            document = decode_aggregate_response(response)
        except (ValueError, UnicodeError, RecursionError):
            return AggregateObservation(**fields, outcome="failed", error_code="invalid_response")
        if type(document.get("code")) is not int:
            return AggregateObservation(**fields, outcome="failed", error_code="invalid_response")
        if document["code"] != 0:
            return AggregateObservation(**fields, outcome="failed", error_code="provider_error")
        meta = document.get("meta")
        if not isinstance(meta, dict):
            return AggregateObservation(**fields, outcome="failed", error_code="invalid_response")
        pagination = meta.get("pagination")
        if not isinstance(pagination, dict):
            return AggregateObservation(**fields, outcome="failed", error_code="invalid_response")
        return total_result(
            "quake", query_id, pagination.get("total"), completed_at, self._data_mode
        )
