"""Run unchanged catalog worker assertions with this package's dedicated catalog fixture.

The old all-content-rollback assertion is retained and expected to expose the
approved durable-response contract change; its failure is never relabeled a skip.
"""

from tests.integration import test_r06_source_worker_pg as legacy
from tests.integration.test_r06_catalog_documents_pg import catalog_engine as _catalog_fixture

catalog_worker_engine = _catalog_fixture
test_legacy_nine_source_registrations = (
    legacy.test_nine_source_registrations_have_one_fixed_identity_and_eight_categories
)
test_legacy_nine_source_jobs = (
    legacy.test_nine_source_jobs_commit_raw_content_evidence_cursor_and_status
)
test_legacy_failures = legacy.test_catalog_failure_never_publishes_partial_page_or_cursor
test_legacy_osv_resume = (
    legacy.test_osv_partial_or_durable_continuation_preserves_post_body_and_resume
)
test_legacy_avid_restart = legacy.test_avid_restart_uses_pinned_tree_and_retains_both_raw_requests
test_legacy_source_identity = (
    legacy.test_conflicting_registered_identity_is_rejected_without_network
)
test_legacy_bad_pages = (
    legacy.test_each_bad_catalog_page_is_blocked_without_business_or_cursor_writes
)
test_legacy_empty_response = (
    legacy.test_valid_empty_catalog_response_is_recorded_without_fabricated_document
)
