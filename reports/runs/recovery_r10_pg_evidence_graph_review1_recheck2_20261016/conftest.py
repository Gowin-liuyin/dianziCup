"""Load fixed repository test guards and failure redaction for isolated review tests."""

import importlib.util
from pathlib import Path

SOURCE = Path('D:/wt/r10-graph-recheck2/backend/tests/conftest.py')
spec = importlib.util.spec_from_file_location('frozen_repository_conftest', SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
isolated_test_database_url = module.isolated_test_database_url
register_sensitive_failure_value = module.register_sensitive_failure_value
pytest_configure = module.pytest_configure
pytest_runtest_makereport = module.pytest_runtest_makereport

