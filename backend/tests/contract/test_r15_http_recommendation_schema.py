"""The adapter uses the root-frozen JSON Schema rather than inventing wire fields."""

import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker

from ai_intel.api.recommendation_contracts import (
    CreateReport,
    CreateSubscription,
    GenerateRecommendations,
    ReplaceSubscription,
    SetSubscriptionEnabled,
)
from ai_intel.api.recommendation_routes import PATHS, build_recommendation_router

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = json.loads(
    (ROOT / "contracts/schemas/recommendation_api_v1.json").read_text(encoding="utf-8")
)


def validator(name):
    return Draft202012Validator(
        {"$ref": "#/$defs/" + name, "$defs": SCHEMA["$defs"]}, format_checker=FormatChecker()
    )


@pytest.mark.parametrize(
    "model,name,raw",
    [
        (CreateSubscription, "CreateSubscription", {"spec": {"product_keys": ["PyPI:alpha"]}}),
        (
            ReplaceSubscription,
            "ReplaceSubscription",
            {"expected_version": 2, "spec": {"risk_topics": ["AML.T0051"]}},
        ),
        (
            SetSubscriptionEnabled,
            "SetSubscriptionEnabled",
            {"expected_version": 1, "enabled": False},
        ),
        (GenerateRecommendations, "GenerateRecommendations", {}),
        (
            CreateReport,
            "CreateReport",
            {"subscription_id": str(uuid4()), "generation_id": str(uuid4()), "frequency": "week"},
        ),
    ],
)
def test_root_schema_and_api_models_accept_same_normalized_fields(model, name, raw):
    assert not list(validator(name).iter_errors(raw))
    result = model.model_validate_json(json.dumps(raw)).model_dump(mode="json")
    assert not list(validator(name).iter_errors(result))
    assert set(result) == set(model.model_fields)


@pytest.mark.parametrize(
    "name,raw",
    [
        ("CreateSubscription", {"spec": {"asset_ids": ["not-uuid"]}}),
        ("CreateSubscription", {"spec": {"product_keys": ["x"], "minimum_priority": True}}),
        ("SetSubscriptionEnabled", {"expected_version": True, "enabled": False}),
        (
            "ReplaceSubscription",
            {"expected_version": 1, "spec": {"product_keys": ["x"]}, "enabled": False},
        ),
        ("GenerateRecommendations", {"cutoff_at": "2026-10-16T00:00:00Z"}),
        (
            "CreateReport",
            {"subscription_id": str(uuid4()), "generation_id": str(uuid4()), "frequency": "month"},
        ),
    ],
)
def test_root_schema_rejects_known_boundary_attacks(name, raw):
    assert list(validator(name).iter_errors(raw))


@pytest.mark.parametrize("prefix", ["/v1", "/api/v1"])
def test_eleven_routes_mounted_at_both_root_owned_prefixes(prefix):
    router = build_recommendation_router(lambda: None, None, None, data_mode="fixture")
    assert len(router.routes) == 11 and not router.prefix
    app = FastAPI()
    app.include_router(router, prefix=prefix)
    client = TestClient(app)
    for method, path, _, _ in PATHS:
        target = (
            path.replace("{subscription_id}", str(uuid4()))
            .replace("{recommendation_id}", str(uuid4()))
            .replace("{report_id}", str(uuid4()))
        )
        query = (
            "?subscription_id=" + str(uuid4())
            if path.startswith("/reports/{") or path.endswith("/read")
            else ""
        )
        body = (
            {"spec": {"product_keys": ["PyPI:alpha"]}}
            if method == "POST" and path == "/subscriptions"
            else {}
        )
        if method == "PATCH":
            body = {"expected_version": 1, "enabled": False}
        if path == "/reports" and method == "POST":
            body = {
                "subscription_id": str(uuid4()),
                "generation_id": str(uuid4()),
                "frequency": "day",
            }
        response = client.request(
            method, prefix + target + query, json=body if method != "GET" else None
        )
        assert response.status_code == 401
        problem = response.json()
        assert response.headers["content-type"] == "application/problem+json"
        assert set(problem) == {
            "type",
            "title",
            "status",
            "detail",
            "instance",
            "trace_id",
            "error",
        }
        assert problem["instance"] == prefix + target
        assert "Max-Age=0" in response.headers["set-cookie"]
