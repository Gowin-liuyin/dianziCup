"""API和worker共享原文存储配置，选择远端时无隐式本地后备。"""

from pathlib import Path

from ai_intel.infrastructure.content_store import ContentStorage, ContentStore
from ai_intel.infrastructure.minio_store import MinioContentStore
from ai_intel.infrastructure.settings import ApplicationSettings


def build_content_storage(settings: ApplicationSettings) -> ContentStorage:
    """固定部署配置决定适配器；初始化不访问网络，不信任请求体提供的目标。"""
    if settings.content_store_backend == "local":
        return ContentStore(Path(settings.raw_content_directory))
    if (
        settings.minio_endpoint is None
        or settings.minio_bucket is None
        or settings.minio_access_key is None
        or settings.minio_secret_key is None
    ):
        raise ValueError("validated MinIO settings are required")
    return MinioContentStore(
        settings.minio_endpoint,
        settings.minio_bucket,
        settings.minio_access_key,
        settings.minio_secret_key,
        secure=settings.minio_secure,
        ca_file=settings.minio_ca_file,
        timeout_seconds=settings.dependency_timeout_seconds,
        test_mode=settings.app_env == "test",
    )
