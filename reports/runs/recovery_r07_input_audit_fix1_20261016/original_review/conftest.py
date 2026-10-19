"""Explicitly load repository failure hooks and register SecretStr for external probes."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
specification = importlib.util.spec_from_file_location('independent_review1_shared_pytest_guard', ROOT / 'backend/tests/conftest.py')
module = importlib.util.module_from_spec(specification)
specification.loader.exec_module(module)
pytest_configure = module.pytest_configure
pytest_runtest_makereport = module.pytest_runtest_makereport
register_sensitive_failure_value = module.register_sensitive_failure_value
isolated_test_database_url = module.isolated_test_database_url
