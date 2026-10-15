"""复跑原始样本时只复用本工作树隔离数据库和秘密脱敏 guard。"""

import importlib.util
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[3] / "backend/tests/conftest.py"
spec = importlib.util.spec_from_file_location("r10_author_repository_guards", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
isolated_test_database_url = module.isolated_test_database_url
register_sensitive_failure_value = module.register_sensitive_failure_value
pytest_configure = module.pytest_configure
pytest_runtest_makereport = module.pytest_runtest_makereport
