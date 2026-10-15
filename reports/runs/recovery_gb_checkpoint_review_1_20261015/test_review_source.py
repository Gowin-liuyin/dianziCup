import pytest
from test_r02_schema_migration import empty_schema_engine as empty_schema_engine
import test_r04_source_documents as original
from ai_intel.infrastructure.database import run_migrations

pytestmark = pytest.mark.real_pg

@pytest.fixture
def page_engine(empty_schema_engine):
    run_migrations(empty_schema_engine.url.render_as_string(hide_password=False))
    return empty_schema_engine

for name in dir(original):
    if name.startswith('test_'):
        globals()[name] = getattr(original, name)
