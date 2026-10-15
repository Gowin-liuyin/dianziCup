"""Keep old test bodies while using the approved new-database, UUID-schema PG fixture."""

import pytest
from tests.integration.test_r06_catalog_documents_pg import catalog_engine


class DedicatedDatabaseFixture:
    def pytest_collectstart(self, collector):
        if isinstance(collector, pytest.Module) and collector.path.name == (
            "test_r04_source_documents.py"
        ):
            collector.obj.page_engine = catalog_engine


raise SystemExit(pytest.main([
    "tests/integration/test_r04_source_documents.py", "-q", "--no-cov",
    "--basetemp=D:/dianzi-local-evidence/r06-bulk-source-evidence/pytest_r04_adapted",
], plugins=[DedicatedDatabaseFixture()]))
