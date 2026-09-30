"""Alembic 迁移环境: 连接串来自 Settings, 不硬编码秘密。"""

from __future__ import annotations

import sys
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_intel.infrastructure.settings import load_application_settings

config = context.config


def _database_url() -> str:
    """优先用迁移配置传入的连接串; 否则回退 Settings; 都没有则明确报错。"""
    configured_url = config.get_main_option("sqlalchemy.url")
    if configured_url:
        return configured_url
    settings = load_application_settings()
    if settings.database_url is None:
        raise RuntimeError("DATABASE_URL is required to run migrations")
    return settings.database_url.get_secret_value()


def run_migrations_offline() -> None:
    """离线模式: 仅生成 SQL, 不连库。"""
    context.configure(url=_database_url(), literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式: 真实连接目标库执行迁移。"""
    engine = create_engine(_database_url())
    with engine.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
