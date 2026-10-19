"""Selected unchanged R05 PG regressions; own database fixture and synthetic model wire."""
from tests.integration.test_r05_question_api_pg import (
    question_api,
    test_same_key_replay_and_conflicting_body_do_not_repeat_generation,
    test_history_becomes_stale_without_overwriting_saved_response,
    test_expired_pending_replay_fails_without_charge_and_late_writer_cannot_publish,
    test_unsupported_r12_scope_is_rejected_without_pg_answer_or_model,
    test_generation_failure_attempt_and_unknown_fee_survive_restart,
    test_answer_owner_and_tenant_are_not_visible_to_other_users,
)
from review_fixtures import vector_database as vector_database
