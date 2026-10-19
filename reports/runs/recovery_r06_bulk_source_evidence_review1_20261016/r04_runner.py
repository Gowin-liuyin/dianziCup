"""Only the legacy R04 resource fixture is adapted to the new isolated database."""

import hashlib
import os
import subprocess
from pathlib import Path

import pytest
from tests.integration.test_r06_catalog_documents_pg import catalog_engine

RUN = Path(__file__).resolve().parent
legacy_file = Path("tests/integration/test_r04_source_documents.py")
frozen = subprocess.check_output(["git", "show", "a89e94b66e240a0c958f7b7e2b8dc22e88f79348:backend/tests/integration/test_r04_source_documents.py"])
assert legacy_file.read_bytes().replace(b"\r\n", b"\n") == frozen
assert hashlib.sha256(frozen).hexdigest() == "a93f181f94312902dca5d23fb85cc1229b3948bb422f8e8faa5e9ed8b120da68"


class ResourceAdapter:
    def pytest_collectstart(self, collector):
        if isinstance(collector, pytest.Module) and collector.path.name == legacy_file.name:
            collector.obj.page_engine = catalog_engine


raise SystemExit(pytest.main([str(legacy_file), "-q", "--no-cov", "--import-mode=importlib", "--junitxml=" + str(RUN / (os.environ["REVIEW_CHECK_LABEL"] + ".xml")), "--basetemp=" + os.environ["REVIEW_BASETEMP"]], plugins=[ResourceAdapter()]))
