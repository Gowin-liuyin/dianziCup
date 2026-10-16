"""Validate optional graph configuration without opening sockets or disclosing credentials."""

import pytest
from pydantic import SecretStr

from ai_intel.infrastructure.settings import load_application_settings


def test_missing_graph_configuration_remains_unconfigured() -> None:
    configuration = load_application_settings(_env_file=None)
    assert configuration.neo4j_uri is None
    assert configuration.neo4j_password is None


@pytest.mark.parametrize("missing", ("neo4j_uri", "neo4j_username", "neo4j_password"))
def test_partial_graph_configuration_is_rejected(missing: str) -> None:
    values = {
        "app_env": "test",
        "neo4j_uri": "bolt://127.0.0.1:27687",
        "neo4j_username": "neo4j",
        "neo4j_password": SecretStr("synthetic-graph-fixture"),
        missing: None,
    }
    with pytest.raises(ValueError, match="configured together"):
        load_application_settings(**values)


@pytest.mark.parametrize(
    "uri",
    (
        "https://graph.invalid",
        "bolt+ssc://graph.invalid",
        "bolt://user:synthetic@graph.invalid",
        "bolt://graph.invalid/private",
        "bolt://graph.invalid?secret=synthetic",
        "bolt://graph.invalid#synthetic",
        "bolt://graph.invalid:0",
        "bolt://graph.invalid:70000",
        "bolt://",
    ),
)
def test_graph_uri_has_no_credentials_paths_or_unsupported_security(uri: str) -> None:
    with pytest.raises(ValueError) as failure:
        load_application_settings(
            app_env="test",
            neo4j_uri=uri,
            neo4j_username="neo4j",
            neo4j_password=SecretStr("synthetic-graph-fixture"),
        )
    assert uri not in str(failure.value)
    assert "synthetic-graph-fixture" not in str(failure.value)


@pytest.mark.parametrize("environment", ("development", "staging", "production"))
def test_plaintext_graph_connection_is_limited_to_test(environment: str) -> None:
    with pytest.raises(ValueError, match="plaintext Neo4j"):
        load_application_settings(
            app_env=environment,
            neo4j_uri="bolt://graph.invalid:7687",
            neo4j_username="neo4j",
            neo4j_password=SecretStr("synthetic-graph-fixture"),
        )


def test_verified_tls_graph_configuration_preserves_secret_wrapper() -> None:
    configuration = load_application_settings(
        app_env="production",
        data_mode="live",
        allowed_origins=("https://ui.invalid",),
        neo4j_uri="bolt+s://graph.invalid:7687",
        neo4j_username="neo4j",
        neo4j_password=SecretStr("synthetic-graph-fixture"),
    )
    assert configuration.neo4j_uri == "bolt+s://graph.invalid:7687"
    assert "synthetic-graph-fixture" not in repr(configuration)


def test_test_graph_allows_an_explicit_local_plaintext_endpoint() -> None:
    configuration = load_application_settings(
        app_env="test",
        neo4j_uri="bolt://127.0.0.1:27687",
        neo4j_username="neo4j",
        neo4j_password=SecretStr("synthetic-graph-fixture"),
    )
    assert configuration.neo4j_uri == "bolt://127.0.0.1:27687"
