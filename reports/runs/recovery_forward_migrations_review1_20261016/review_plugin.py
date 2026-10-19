"""仅将作者测试输出指向审查目录，并接入既有隔离守卫。"""

from pathlib import Path
from sqlalchemy.engine import make_url
from scripts.dev import require_isolated_test_database

RUN = Path(__file__).resolve().parent


def controlled_test_url():
    return make_url(require_isolated_test_database()).set(drivername='postgresql+psycopg')


def pytest_collection_modifyitems(items):
    for item in items:
        module = item.module
        if module.__name__.endswith('test_recovery_forward_migrations_0023_0026_pg'):
            module.RUN = RUN/'pg_author'
            module.MARKER = 'recovery_forward_migrations_review1_20261016:'
            module.controlled_test_url = controlled_test_url

