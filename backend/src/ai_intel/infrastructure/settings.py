"""应用配置分层: APP_ENV 与 DATA_MODE 分离, 秘密引用与非秘密配置分离。

职责: 加载并校验运行配置; 缺必需项给出可定位错误; production 拒绝 fixture 数据模式
与默认开发秘密, 避免开发配置静默进入生产。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.exceptions import SettingsError

DEVELOPMENT_SECRET_PLACEHOLDERS = frozenset(
    {
        "dev-only-not-a-secret",
        "changeme",
        "password",
    }
)

AppEnvironment = Literal["development", "test", "staging", "production"]
DataMode = Literal["fixture", "live"]


class ConfigurationError(ValueError):
    """配置错误: 消息必须指出具体字段与原因, 不吞掉原始校验失败。"""


class ApplicationSettings(BaseSettings):
    """运行配置: 非秘密项直接读取, 秘密项以 SecretStr 承载且只存引用。"""

    model_config = SettingsConfigDict(env_file=None, extra="ignore", hide_input_in_errors=True)

    app_env: AppEnvironment = Field(default="development")
    data_mode: DataMode = Field(default="live")
    database_url: SecretStr | None = None
    redis_url: SecretStr | None = None
    opensearch_url: str | None = None
    opensearch_username: str | None = None
    opensearch_password: SecretStr | None = None
    opensearch_ca_file: str | None = None
    auth_secret_ref: SecretStr | None = None
    allowed_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:25173")
    dependency_timeout_seconds: float = Field(default=3.0, gt=0, le=10)
    raw_content_directory: str = "var/raw"
    dns_resolver: Literal["system", "cloudflare_doh"] = "system"
    content_store_backend: Literal["local", "minio"] = "local"
    minio_endpoint: str | None = None
    minio_bucket: str | None = None
    minio_access_key: SecretStr | None = None
    minio_secret_key: SecretStr | None = None
    minio_secure: bool = True
    minio_ca_file: str | None = None
    generation_provider: Literal["deepseek_openai", "deepseek_anthropic", "openai", "anthropic"] = (
        "deepseek_openai"
    )
    generation_model: str = Field(default="deepseek-flash", min_length=1, max_length=200)
    generation_api_key: SecretStr | None = None
    revalidation_cursor_signing_key: SecretStr | None = None
    semantic_model_cache_directory: Path | None = None
    hybrid_generation_id: str = Field(default="e5-v1", pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    hybrid_index_name: str = Field(
        default="dianzi_e5_v1", pattern=r"^dianzi_[a-z0-9][a-z0-9_-]{1,180}$"
    )
    source_polling_enabled: bool = False
    enrichment_generation_enabled: bool = False
    enrichment_private_egress_granted: bool = False
    enrichment_aggregate_enabled: bool = False

    @model_validator(mode="after")
    def validate_revalidation_cursor_signing_key(self) -> ApplicationSettings:
        """Workers share a persisted 32-byte key; missing configuration grants no cursor service."""
        if self.revalidation_cursor_signing_key is None:
            return self
        value = self.revalidation_cursor_signing_key.get_secret_value()
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ConfigurationError("REVALIDATION_CURSOR_SIGNING_KEY must encode 32 bytes")
        if self.app_env in {"staging", "production"} and value in {
            bytes(32).hex(),
            bytes([1] * 32).hex(),
            bytes(range(32)).hex(),
        }:
            raise ConfigurationError("REVALIDATION_CURSOR_SIGNING_KEY cannot use a fixture key")
        return self

    @model_validator(mode="after")
    def validate_enrichment_execution_authority(self) -> ApplicationSettings:
        """Credential presence grants no background calls or private evidence egress."""
        if self.enrichment_private_egress_granted and not self.enrichment_generation_enabled:
            raise ConfigurationError("private enrichment egress requires enabled generation")
        if not self.enrichment_generation_enabled:
            return self
        if self.generation_api_key is None or not self.generation_api_key.get_secret_value():
            raise ConfigurationError("enrichment generation requires a nonempty credential")
        if re.fullmatch(r"[a-zA-Z0-9_.:/-]{1,200}", self.generation_model) is None:
            raise ConfigurationError("invalid enrichment generation model")
        if (
            self.generation_provider.startswith("deepseek")
            and self.generation_model != "deepseek-flash"
        ):
            raise ConfigurationError("unapproved DeepSeek enrichment model")
        return self

    @model_validator(mode="after")
    def validate_content_store_configuration(self) -> ApplicationSettings:
        """对象服务缺配置即拒绝，不以本地目录悄悄替代远端原文库。"""
        if self.content_store_backend != "minio":
            return self
        if not self.minio_endpoint or not self.minio_bucket:
            raise ConfigurationError("MinIO endpoint and bucket are required")
        if (
            self.minio_access_key is None
            or self.minio_secret_key is None
            or not self.minio_access_key.get_secret_value()
            or not self.minio_secret_key.get_secret_value()
        ):
            raise ConfigurationError("MinIO credentials are required")
        parsed = urlsplit("https://" + self.minio_endpoint)
        try:
            port = parsed.port
        except ValueError:
            raise ConfigurationError(
                "MINIO_ENDPOINT must be a hostname with optional port"
            ) from None
        if (
            not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
            or (port is not None and port < 1)
        ):
            raise ConfigurationError("MINIO_ENDPOINT must be a hostname with optional port")
        if not self.minio_secure and self.app_env != "test":
            raise ConfigurationError("plaintext MinIO is allowed only when APP_ENV=test")
        return self

    @model_validator(mode="after")
    def validate_search_connection_security(self) -> ApplicationSettings:
        """CA显式注入；认证独立于URL，不能关闭TLS或回显秘密以绕过健康检查。"""
        if (self.opensearch_username is None) != (self.opensearch_password is None):
            raise ConfigurationError(
                "OPENSEARCH_USERNAME and OPENSEARCH_PASSWORD must be configured together"
            )
        if self.opensearch_username is not None and (
            not self.opensearch_username.strip()
            or self.opensearch_password is None
            or not self.opensearch_password.get_secret_value()
        ):
            raise ConfigurationError("OpenSearch credentials must be non-empty")
        if self.opensearch_url is not None:
            try:
                parsed = urlsplit(self.opensearch_url)
                port = parsed.port
                if (
                    parsed.scheme not in {"http", "https"}
                    or not parsed.hostname
                    or parsed.username is not None
                    or parsed.password is not None
                    or parsed.query
                    or parsed.fragment
                    or (port is not None and port < 1)
                ):
                    raise ValueError
            except ValueError:
                raise ConfigurationError(
                    "OPENSEARCH_URL must be an http(s) origin without credentials"
                ) from None
            if self.app_env == "production" and parsed.scheme != "https":
                raise ConfigurationError("OPENSEARCH_URL requires HTTPS in production")
        return self

    @model_validator(mode="after")
    def reject_unsafe_allowed_origins(self) -> ApplicationSettings:
        """凭据跨域只允许精确Origin；不接受通配、路径或用户信息。"""
        if not self.allowed_origins:
            raise ConfigurationError("ALLOWED_ORIGINS must contain at least one exact origin")
        for origin in self.allowed_origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
                or "*" in origin
            ):
                raise ConfigurationError("ALLOWED_ORIGINS requires exact http(s) origins")
            if self.app_env == "production" and parsed.scheme != "https":
                raise ConfigurationError("ALLOWED_ORIGINS requires HTTPS in production")
        return self

    @model_validator(mode="after")
    def production_must_not_use_fixture_or_placeholder_secrets(self) -> ApplicationSettings:
        """production 拒绝 fixture 数据模式与默认开发秘密; 违规必须显式报错。"""
        if self.app_env != "production":
            return self
        problems: list[str] = []
        if self.data_mode == "fixture":
            problems.append("DATA_MODE=fixture is not allowed when APP_ENV=production")
        database_secret = self.database_url.get_secret_value() if self.database_url else ""
        for placeholder in DEVELOPMENT_SECRET_PLACEHOLDERS:
            if placeholder in database_secret:
                problems.append(
                    "DATABASE_URL contains a development placeholder secret, "
                    "which is not allowed when APP_ENV=production"
                )
                break
        if problems:
            raise ConfigurationError("; ".join(problems))
        return self


def load_application_settings(**overrides: object) -> ApplicationSettings:
    """构造并校验配置; 缺必需项或组合违规时抛出 ConfigurationError。"""
    try:
        return ApplicationSettings.model_validate(overrides)
    except ValidationError as validation_error:
        reasons: list[str] = []
        for error in validation_error.errors(include_input=False, include_url=False):
            cause = error.get("ctx", {}).get("error")
            if isinstance(cause, ConfigurationError):
                reasons.append(str(cause))
            else:
                field = error["loc"][0] if error["loc"] else "configuration"
                reasons.append(f"invalid setting: {field}")
        raise ConfigurationError("; ".join(reasons)) from None
    except SettingsError:
        raise ConfigurationError("invalid environment settings; check field types") from None


def describe_dependency_readiness(settings: ApplicationSettings) -> dict[str, str]:
    """按配置声明依赖就绪状态; 未配置的搜索依赖如实标为降级而非就绪。"""
    readiness = {
        "database": "configured" if settings.database_url else "not_configured",
        "cache": "configured" if settings.redis_url else "not_configured",
        "search": "configured" if settings.opensearch_url else "degraded_search_not_configured",
    }
    return readiness
