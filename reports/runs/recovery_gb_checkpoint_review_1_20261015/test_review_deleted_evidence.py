import pytest
from sqlalchemy import delete, select
from test_r05_question_api_pg import question_api as question_api, post_question, stored_answer
from test_r05_vector_persistence import vector_database as vector_database
from ai_intel.knowledge.models import evidence
from ai_intel.knowledge.persistence_models import claim_evidence
from ai_intel.retrieval.persistence_models import retrieval_chunks

pytestmark = pytest.mark.real_pg

def test_physical_removal_of_all_evidence_blocks_new_fact_and_old_citation(question_api):
    api = question_api
    before = post_question(api,key='independent-physical-evidence-before')
    assert before.status_code == 200
    original_response = before.json()
    with api['engine'].begin() as connection:
        identifiers = tuple(connection.scalars(select(evidence.c.evidence_id)))
        assert identifiers
        connection.execute(delete(retrieval_chunks))
        connection.execute(delete(claim_evidence))
        connection.execute(delete(evidence))
    after = post_question(api,key='independent-physical-evidence-after')
    assert after.status_code == 503
    assert after.json()['error']['code'] == 'answer_evidence_unavailable'
    assert len(api['wire'].calls) == 2
    historical = api['client'].get('/v1/answers/' + original_response['answer_id'])
    assert historical.status_code == 404
    with api['engine'].connect() as connection:
        from ai_intel.retrieval.persistence_models import grounded_answers
        preserved = connection.scalar(select(grounded_answers.c.response).where(grounded_answers.c.answer_id == original_response['answer_id']))
    assert preserved == original_response
