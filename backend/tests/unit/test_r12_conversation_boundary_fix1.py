"""Unbound references clarify; explicit first questions preserve bounded input semantics."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from ai_intel.answering.conversation_context import resolve_question_context
from ai_intel.answering.conversation_contracts import EventReference
from ai_intel.api.question_contracts import QuestionRequest
from ai_intel.domain.access import AccessScope, Role

SCOPE = AccessScope.for_authenticated_user("synthetic-owner", "tenant-a", Role.ANALYST)
EVENT = UUID("00000000-0000-0000-0000-000000000001")


@pytest.mark.parametrize("question", ["它的修复是什么？", "另一个呢？", "What is its fix?"])
def test_unbound_reference_has_no_derived_query(question):
    context = resolve_question_context(
        QuestionRequest(question=question, mode="library"),
        conversation_id=EVENT,
        base_version=0,
        scope=SCOPE,
        event_references=(),
        now=datetime.now(UTC),
    )
    assert context.clarification_code == "reference_ambiguous"
    assert context.retrieval_queries == ()


@pytest.mark.parametrize(
    ("question", "explicit_events"),
    [
        ("CVE-2026-10001: what is its fix?", ()),
        ("它的修复是什么？", (EVENT,)),
        ("Describe current security facts", ()),
    ],
)
def test_explicit_or_nonreferential_first_question_is_not_rejected(question, explicit_events):
    context = resolve_question_context(
        QuestionRequest(question=question, event_ids=explicit_events, mode="library"),
        conversation_id=EVENT,
        base_version=0,
        scope=SCOPE,
        event_references=(
            EventReference(event_id=EVENT, identifiers=("CVE-2026-10001",), business_version=1),
        ),
        now=datetime.now(UTC),
    )
    assert context.clarification_code is None
    assert context.retrieval_queries[0].text == question
