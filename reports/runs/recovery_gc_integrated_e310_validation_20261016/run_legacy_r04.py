"""Preserve original test bytes and expectations; adapt only the independent resource fixture."""
import pytest
from pathlib import Path
from tests.integration.test_r06_catalog_documents_pg import catalog_engine


class IndependentDatabaseFixture:
    def pytest_collectstart(self,collector):
        if isinstance(collector,pytest.Module) and collector.path.name=='test_r04_source_documents.py':
            collector.obj.page_engine=catalog_engine


run=Path(__file__).resolve().parent
raise SystemExit(pytest.main(['tests/integration/test_r04_source_documents.py','--no-cov','-q','--tb=short',
    '-p','no:cacheprovider','--basetemp',str(run/'legacy_r04_adapted_tmp'),
    '--junitxml',str(run/'pg_original_r04_resource_adapted.xml')],plugins=[IndependentDatabaseFixture()]))
