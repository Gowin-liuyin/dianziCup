"""Run unchanged R11 PG behaviors against production head using a head-aware fixture."""

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text

ORIGINAL_PATH = Path(__file__).with_name("test_t24_asset_inventory.py")
SPEC = importlib.util.spec_from_file_location("original_t24_migration_regression", ORIGINAL_PATH)
ORIGINAL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ORIGINAL)

for name in dir(ORIGINAL):
    if name.startswith("test_") or name == "inventory_api":
        globals()[name] = getattr(ORIGINAL, name)

pytestmark = pytest.mark.real_pg


@pytest.fixture
def inventory_engine(migrated_engine):
    """The original assertions run unchanged; only the original revision guard is adapted."""
    with migrated_engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "0019_aggregate_observations"
        )
        assert connection.scalar(text("SELECT to_regclass('asset_snapshots')")) is not None
    return migrated_engine
