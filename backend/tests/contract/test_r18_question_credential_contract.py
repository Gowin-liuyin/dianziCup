"""The internal credential seam preserves strict public question and answer contracts."""

import inspect
from collections.abc import Callable
from typing import get_type_hints
from uuid import uuid4

import pytest
from pydantic import ValidationError

from ai_intel.answering.grounding import generate_grounded_answer
from ai_intel.answering.service import GroundedQuestionService, read_grounded_answer
from ai_intel.api.actor_references import ActorReference
from ai_intel.api.question_contracts import QuestionRequest
from ai_intel.retrieval.service import EventEvidenceRetriever


def test_original_cookie_keyword_and_optional_internal_hooks_are_compatible():
    for target in (GroundedQuestionService.ask, read_grounded_answer):
        parameter = inspect.signature(target).parameters["session_token"]
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
        assert get_type_hints(target)["session_token"] == str | ActorReference
    credential = inspect.signature(GroundedQuestionService.ask).parameters["credential"]
    assert credential.kind is inspect.Parameter.KEYWORD_ONLY and credential.default is None
    for target, name in (
        (generate_grounded_answer, "before_call"),
        (EventEvidenceRetriever.retrieve, "before_io"),
    ):
        hook = inspect.signature(target).parameters[name]
        assert hook.kind is inspect.Parameter.KEYWORD_ONLY and hook.default is None
        assert get_type_hints(target)[name] == Callable[[], None] | None


def test_trusted_mode_seams_keep_live_default_and_static_current_reader():
    for target in (EventEvidenceRetriever.__init__, EventEvidenceRetriever.require_current):
        parameter = inspect.signature(target).parameters["data_mode"]
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY and parameter.default == "live"
    assert isinstance(
        inspect.getattr_static(EventEvidenceRetriever, "require_current"), staticmethod
    )


@pytest.mark.parametrize("field", ["tenant_id", "user_id", "role", "credential", "actor_reference"])
def test_public_question_cannot_supply_internal_identity(field):
    with pytest.raises(ValidationError):
        QuestionRequest.model_validate(
            {"question": "fixture question", "event_ids": [str(uuid4())], field: "fixture-spoof"}
        )
