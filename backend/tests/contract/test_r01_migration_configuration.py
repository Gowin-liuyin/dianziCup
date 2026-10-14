"""仅验证迁移配置序列化，合成URL不连接数据库、不执行downgrade。"""

import pytest
from alembic.config import Config

from ai_intel.infrastructure import database


@pytest.mark.parametrize("operation", ["upgrade", "downgrade"])
def test_url_percent_encoding_survives_alembic_configuration(
    monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    seen: list[str] = []
    synthetic_url = "postgresql+psycopg://test_user:synthetic%40password@127.0.0.1:25432/test_dianzi_synthetic?options=-csearch_path%3Dpublic"

    def record_configuration(config: Config, revision: str) -> None:
        seen.append(config.get_main_option("sqlalchemy.url"))
        assert revision == "head"

    monkeypatch.setattr(database.command, operation, record_configuration)
    if operation == "upgrade":
        database.run_migrations(synthetic_url)
    else:
        database.run_downgrade(synthetic_url, "head")
    assert seen == [synthetic_url]
