"""应用配置分层: APP_ENV 与 DATA_MODE 分离, 秘密引用与非秘密配置分离。

职责: 加载并校验运行配置; 缺必需项给出可定位错误; production 拒绝 fixture 数据模式
与默认开发秘密, 避免开发配置静默进入生产。
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: AppEnvironment = Field(default="development")
    data_mode: DataMode = Field(default="fixture")
    database_url: SecretStr | None = None
    redis_url: str | None = None
    opensearch_url: str | None = None
    auth_secret_ref: SecretStr | None = None

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
        return ApplicationSettings(**overrides)  # type: ignore[arg-type]
    except ValueError as validation_error:
        raise ConfigurationError(str(validation_error)) from validation_error


def describe_dependency_readiness(settings: ApplicationSettings) -> dict[str, str]:
    """按配置声明依赖就绪状态; 未配置的搜索依赖如实标为降级而非就绪。"""
    readiness = {
        "database": "configured" if settings.database_url else "not_configured",
        "cache": "configured" if settings.redis_url else "not_configured",
        "search": "configured" if settings.opensearch_url else "degraded_search_not_configured",
    }
    return readiness
