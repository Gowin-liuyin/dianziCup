"""All original 25 test function objects are unchanged; only module-owned PG fixture is replaced."""

import os

import pytest
from sqlalchemy import MetaData, Table, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool
from tests.r11_forward_fixtures import forbid_business_table_creation, forbid_metadata_creation

import original_probe_frozen as original
from ai_intel.infrastructure.database import run_migrations

for name in dir(original):
    if name.startswith("test_"):
        globals()[name] = getattr(original, name)

api = original.api
upload = original.upload
path = original.path
row_counts = original.row_counts
document = original.document
spdx_document = original.spdx_document
raw_document = original.raw_document


@pytest.fixture(scope="module")
def default_engine():
    url = make_url(os.environ["TEST_DATABASE_URL"])
    assert url.database == "test_dianzi_r11_int_rev1_fix1_20261016"
    assert (url.host, url.port) == ("127.0.0.1", 25432)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(MetaData, "create_all", forbid_metadata_creation)
        patch.setattr(Table, "create", forbid_business_table_creation)
        run_migrations(url.render_as_string(hide_password=False))
    engine = create_engine(url, hide_parameters=True, poolclass=NullPool)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0022_sbom_sidecars"
    yield engine
    engine.dispose()
