"""Hunter fixed product-name searches retain only the documented data.total field."""

from __future__ import annotations

import base64
from datetime import datetime
from types import MappingProxyType
from typing import Literal
from urllib.parse import urlencode

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

HUNTER_QUERIES = MappingProxyType({"ollama": 'app.name="Ollama"', "vllm": 'app.name="vLLM"'})
HUNTER_ENDPOINT = "https://hunter.qianxin.com/openApi/search"


class HunterAggregateConnector:
    """One GET without retries, redirects, account probing or caller-supplied query text."""

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
            self._gateway = build_aggregate_gateway("hunter", api_key, dns_resolver)

    def collect(
        self, query_id: AggregateQueryId, *, retrieved_at: datetime | None = None
    ) -> AggregateObservation:
        require_query_id(query_id)
        if retrieved_at is not None and self._data_mode != "fixture":
            raise ValueError("retrieved_at override requires explicit fixture mode")
        completed_at = retrieval_time(retrieved_at)
        fields: AggregateIdentity = {
            "provider": "hunter",
            "query_id": query_id,
            "retrieved_at": completed_at,
            "data_mode": self._data_mode,
        }
        if self._gateway is None:
            return AggregateObservation(
                **fields, outcome="not_configured", error_code="credential_missing"
            )
        encoded_query = base64.urlsafe_b64encode(HUNTER_QUERIES[query_id].encode()).decode("ascii")
        request_url = (
            HUNTER_ENDPOINT
            + "?"
            + urlencode(
                {
                    "search": encoded_query,
                    "page": 1,
                    "page_size": 1,
                    "is_web": 3,
                    "fields": "updated_at",
                }
            )
        )
        try:
            response = self._gateway.fetch(request_url, max_redirect_hops=0)
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
        if document["code"] != 200:
            return AggregateObservation(**fields, outcome="failed", error_code="provider_error")
        aggregate_data = document.get("data")
        if not isinstance(aggregate_data, dict):
            return AggregateObservation(**fields, outcome="failed", error_code="invalid_response")
        return total_result(
            "hunter", query_id, aggregate_data.get("total"), completed_at, self._data_mode
        )
