"""数据库引擎、会话边界与迁移执行。

职责: 提供每请求独立 Session 与显式事务边界; 迁移经 alembic 程序化配置执行,
不在生产路径自动 drop/create。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from ai_intel.infrastructure.settings import ApplicationSettings

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"


class MissingDatabaseUrlError(RuntimeError):
    """数据库连接串未配置: 明确报错, 不静默回退到默认库。"""


def build_engine(settings: ApplicationSettings) -> Engine:
    """按配置构建同步引擎; 每请求独立 Session 的基础。"""
    if settings.database_url is None:
        raise MissingDatabaseUrlError("DATABASE_URL is required for persistence")
    database_url = make_url(settings.database_url.get_secret_value())
    if database_url.get_backend_name() != "postgresql":
        raise MissingDatabaseUrlError("DATABASE_URL must use PostgreSQL")
    return create_engine(
        database_url.set(drivername="postgresql+psycopg"),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_timeout=settings.dependency_timeout_seconds,
        connect_args={
            "connect_timeout": max(1, int(settings.dependency_timeout_seconds)),
            "options": f"-c statement_timeout={int(settings.dependency_timeout_seconds * 1000)} "
            f"-c lock_timeout={int(settings.dependency_timeout_seconds * 1000)}",
        },
    )


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    """请求/任务级会话边界: 显式提交或回滚, 会话不跨线程共享。"""
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def run_migrations(database_url: str, target_revision: str = "head") -> None:
    """执行迁移到目标版本; 供空库升级与既有数据升级复用, 版本记录在 alembic_version。"""
    alembic_config = Config()
    alembic_config.set_main_option("script_location", str(MIGRATIONS_DIR))
    alembic_config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(alembic_config, target_revision)


def run_downgrade(database_url: str, target_revision: str) -> None:
    """回滚到指定版本; 回滚失败由 alembic 原样抛出, 不吞异常。"""
    alembic_config = Config()
    alembic_config.set_main_option("script_location", str(MIGRATIONS_DIR))
    alembic_config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.downgrade(alembic_config, target_revision)


def current_migration_revision(database_url: str) -> str | None:
    """读取当前迁移版本号; 未初始化的库返回 None。"""
    from sqlalchemy import text

    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            exists = connection.execute(
                text("SELECT to_regclass(:name)"), {"name": "alembic_version"}
            ).scalar()
            if exists is None:
                return None
            return connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
    finally:
        engine.dispose()
