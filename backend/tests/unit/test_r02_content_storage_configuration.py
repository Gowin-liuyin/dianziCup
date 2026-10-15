"""原文适配器只按可信配置选择；远端错误无本地后备。"""

from pathlib import Path

import pytest
from pydantic import SecretStr

from ai_intel.infrastructure.content_storage_factory import build_content_storage
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.minio_store import MinioContentStore
from ai_intel.infrastructure.settings import ConfigurationError, load_application_settings


def test_local_backend_preserves_existing_content_addressed_interface(tmp_path: Path) -> None:
    store = build_content_storage(load_application_settings(raw_content_directory=str(tmp_path)))
    assert isinstance(store, ContentStore)
    saved = store.store_bytes(b"fixture local content")
    assert store.read_verified(saved.content_hash) == b"fixture local content"


def test_minio_configuration_never_selects_a_local_fallback() -> None:
    settings = load_application_settings(
        app_env="test",
        content_store_backend="minio",
        minio_secure=False,
        minio_endpoint="127.0.0.1:29400",
        minio_bucket="test-dianzi-r02-unit",
        minio_access_key=SecretStr("fixture-unit-access"),
        minio_secret_key=SecretStr("fixture-unit-secret"),
    )
    assert isinstance(build_content_storage(settings), MinioContentStore)


def test_incomplete_minio_configuration_fails_without_echoing_input() -> None:
    with pytest.raises(ConfigurationError, match="endpoint and bucket are required"):
        load_application_settings(content_store_backend="minio")
    with pytest.raises(ConfigurationError, match="credentials are required"):
        load_application_settings(
            content_store_backend="minio",
            minio_endpoint="storage:9000",
            minio_bucket="test-dianzi-r02-unit",
        )


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://storage:9000",
        "user:secret@storage:9000",
        "storage:9000/path",
        "storage:9000?key=value",
        "storage:bad",
        "storage:0",
    ],
)
def test_minio_endpoint_rejects_user_info_paths_and_invalid_ports(endpoint: str) -> None:
    with pytest.raises(ConfigurationError):
        load_application_settings(
            content_store_backend="minio",
            minio_endpoint=endpoint,
            minio_bucket="test-dianzi-r02-unit",
            minio_access_key=SecretStr("fixture-access"),
            minio_secret_key=SecretStr("fixture-secret"),
        )


def test_plaintext_object_storage_requires_explicit_test_environment() -> None:
    with pytest.raises(ConfigurationError, match="APP_ENV=test"):
        load_application_settings(
            app_env="production",
            content_store_backend="minio",
            minio_secure=False,
            minio_endpoint="storage:9000",
            minio_bucket="test-dianzi-r02-unit",
            minio_access_key=SecretStr("fixture-access"),
            minio_secret_key=SecretStr("fixture-secret"),
        )
