"""PG存储运行观测；仅证明组件最近执行，不替代事实或任务状态。"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from ai_intel.knowledge.models import runtime_observations

RUNTIME_MAX_AGE_SECONDS = 45


def record_runtime_observation(engine: Engine, component: str, observed_at: datetime) -> None:
    """实际执行成功后更新观测；PG失败抛出，不能先写假就绪。"""
    if component not in {"worker", "scheduler"}:
        raise ValueError("unsupported runtime component")
    statement = insert(runtime_observations).values(
        component=component, observed_at=observed_at, platform_version="0.1.0"
    )
    with engine.begin() as connection:
        connection.execute(
            statement.on_conflict_do_update(
                index_elements=[runtime_observations.c.component],
                set_={"observed_at": observed_at, "platform_version": "0.1.0"},
            )
        )


def read_runtime_readiness(engine: Engine, now: datetime) -> dict[str, dict[str, str]]:
    """未观测、过期或时钟在未来均不就绪；只返回固定组件与状态。"""
    with engine.connect() as connection:
        rows = connection.execute(
            select(runtime_observations.c.component, runtime_observations.c.observed_at)
        ).all()
        observed: dict[str, datetime] = {str(row[0]): row[1] for row in rows}
    earliest = now - timedelta(seconds=RUNTIME_MAX_AGE_SECONDS)
    return {
        component: {
            "state": "ready"
            if component in observed and earliest <= observed[component].astimezone(UTC) <= now
            else "not_observed_or_stale"
        }
        for component in ("worker", "scheduler")
    }
