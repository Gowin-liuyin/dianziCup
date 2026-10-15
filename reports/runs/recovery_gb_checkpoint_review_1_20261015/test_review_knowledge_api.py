import pytest
from test_r02_schema_migration import empty_schema_engine as empty_schema_engine
from test_r04_knowledge_api_pg import clients as clients
from test_r04_api_review_regressions import default_pg_client as default_pg_client
import test_r04_knowledge_api_pg as original
import test_r04_api_review_regressions as regressions
from ai_intel.infrastructure.database import run_migrations

pytestmark = pytest.mark.real_pg

@pytest.fixture
def api_engine(empty_schema_engine):
    run_migrations(empty_schema_engine.url.render_as_string(hide_password=False))
    return empty_schema_engine

for module in (original,regressions):
    for name in dir(module):
        if name.startswith('test_'):
            globals()[name] = getattr(module,name)
