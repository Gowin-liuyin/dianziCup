"""Different Unicode fixture input proves ranges bind to characters and full omissions."""

import hashlib
import json

import pytest
from tests.unit.test_r07_model_fields import context, fixture_documents
from ai_intel.domain.values import VisibilityScope
from ai_intel.enrichment.evidence_selection import select_field_evidence
from ai_intel.enrichment.job_types import DocumentSnapshot, FieldEvidenceSelectionAudit, FrozenEnrichmentInputs, validate_input_selection


@pytest.mark.parametrize('mutation', ['none', 'byte_offset', 'missing_complement', 'changed_text'])
def test_selected_unicode_offsets_and_complements_reject_wrong_actual_input(mutation):
    document = fixture_documents()[0]
    line = 'Affected 产品🙂 version 1.0.\n'
    text = '背景🙂' * 6000 + '\n' + line
    block = document.blocks[0].model_copy(update={'text': text, 'text_sha256': hashlib.sha256(text.encode()).hexdigest()})
    document = document.model_copy(update={'blocks': (block,), 'json_payload': None})
    frozen = FrozenEnrichmentInputs(context=context((document,)), scope=VisibilityScope(visibility='public'), documents=(DocumentSnapshot.model_validate(document.model_dump()),), parents=())
    actual = FieldEvidenceSelectionAudit.from_selection(select_field_evidence((document,), 'versions'))
    assert actual.selected[0].start_offset == 18001
    assert actual.selected[0].start_offset != 60001
    assert '背景🙂' not in actual.model_dump_json() and '产品🙂' in actual.texts[1]
    if mutation == 'none':
        validate_input_selection(actual, frozen)
        return
    payload = actual.model_dump(mode='json')
    if mutation == 'byte_offset':
        payload['selected'][0]['start_offset'] = 60001
        payload['selected'][0]['end_offset'] = 60002
    elif mutation == 'missing_complement':
        payload['omitted_ranges'] = payload['omitted_ranges'][1:]
    else:
        sent = json.loads(payload['texts'][1])
        sent['text'] = sent['text'].replace('产品🙂', '伪造🙂')
        payload['texts'][1] = json.dumps(sent)
    with pytest.raises(ValueError):
        validate_input_selection(FieldEvidenceSelectionAudit.model_validate_json(json.dumps(payload)), frozen)
