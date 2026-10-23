"""The fixture story interval must match 1.4.1 and exclude the fixed 1.4.2."""

from ai_intel.assessment.version_ranges import contains_version
from ai_intel.domain.enrichment_values import VersionInterval


def test_main_path_story_range_distinguishes_the_two_fixture_versions() -> None:
    interval = VersionInterval(introduced="1.0", fixed="1.4.2")
    affected = contains_version("1.4.1", interval, scheme="pep440", ecosystem="PyPI")
    unaffected = contains_version("1.4.2", interval, scheme="pep440", ecosystem="PyPI")
    assert affected.status == "affected"
    assert unaffected.status == "not_affected"
