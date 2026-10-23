"""The main-path story must refuse live mode before any database call."""

import pytest

from ai_intel.fixtures.main_path_story import (
    FixtureModeRequired,
    load_main_path_story,
    require_fixture_mode,
)


class _Database:
    def connect(self):
        raise AssertionError("live mode opened a database")

    def begin(self):
        raise AssertionError("live mode opened a transaction")


def test_require_fixture_mode_rejects_live_and_unknown() -> None:
    require_fixture_mode("fixture")
    with pytest.raises(FixtureModeRequired):
        require_fixture_mode("live")
    with pytest.raises(FixtureModeRequired):
        require_fixture_mode("")


def test_live_story_load_does_not_open_database() -> None:
    with pytest.raises(FixtureModeRequired):
        load_main_path_story(_Database(), store=None, data_mode="live", analyst_password="unused")
