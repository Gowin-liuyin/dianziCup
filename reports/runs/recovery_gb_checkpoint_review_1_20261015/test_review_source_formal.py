import pytest
from test_review_knowledge_api import api_engine as api_engine, clients as clients
from test_r02_schema_migration import empty_schema_engine as empty_schema_engine
import test_r04_source_http_idempotency_pg as original

pytestmark = pytest.mark.real_pg

for name in dir(original):
    if name.startswith('test_'):
        globals()[name] = getattr(original,name)
