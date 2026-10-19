"""Independent complete/none-confirmed qualification failures from the frozen contract."""
from __future__ import annotations
import copy

import pytest
from pydantic import ValidationError
from test_independent_models import STACK, parse_public, valid_in_schema

@pytest.mark.parametrize('gap',['supported_without_grade','excluded_without_citations','excluded_without_assessment'])
def test_complete_cannot_replace_missing_grade_or_exclusion_support_with_none_confirmed(gap: str) -> None:
    payload=copy.deepcopy(STACK)
    payload['risk_summary']['findings']=[]
    assessment=payload['result']['results'][0]
    if gap=='excluded_without_citations':
        assessment.update(status='excluded_with_evidence',citations=[])
    elif gap=='excluded_without_assessment':
        assessment.update(status='excluded_with_evidence',assessment_id=None)
    assert valid_in_schema('StackCheckEnvelope',payload)
    with pytest.raises(ValidationError):
        parse_public('StackCheckEnvelope',payload)

@pytest.mark.parametrize('gap',['unknown_component','missing_grade'])
def test_partial_unknown_does_not_become_none_confirmed(gap: str) -> None:
    payload=copy.deepcopy(STACK)
    payload['risk_summary'].update(coverage='partial',unknown_component_indices=[0],findings=[])
    if gap=='unknown_component':
        payload['result']['results'][0].update(status='insufficient_evidence',reason_code='missing_version')
    assert valid_in_schema('StackCheckEnvelope',payload)
    with pytest.raises(ValidationError):
        parse_public('StackCheckEnvelope',payload)
