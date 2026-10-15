"""Hard exit at the first simulated paid wire, against the parent's UUID-isolated schema."""
import json
import os
from pydantic import SecretStr
from sqlalchemy import create_engine
from ai_intel.answering.service import GroundedQuestionService
from ai_intel.api.question_contracts import QuestionRequest
from ai_intel.domain.access import AccessScope, Role
from ai_intel.infrastructure.models.generation import GenerationClient, GenerationLimits
from ai_intel.retrieval.service import EventEvidenceRetriever
import sys
sys.path.insert(0, 'D:/wt/r05-pipe-review/backend/tests/integration')
from test_r05_vector_persistence import FixtureSemanticModels
engine = create_engine(os.environ['REVIEW_ISOLATED_DATABASE_URL'])
client = GenerationClient('deepseek_openai', 'deepseek-flash', SecretStr('review-crash-explicit-synthetic-credential'), limits=GenerationLimits(total_timeout_seconds=30.0, max_calls=1))
def simulated_paid_call(*args, **kwargs):
    os._exit(73)
client._gateway.post_json = simulated_paid_call
scope = AccessScope.for_authenticated_user(os.environ['REVIEW_USER_ID'], os.environ['REVIEW_TENANT_ID'], Role.VIEWER)
service = GroundedQuestionService(engine, EventEvidenceRetriever(engine, FixtureSemanticModels()), client, data_mode='fixture')
service.ask(QuestionRequest.model_validate_json(os.environ['REVIEW_PAYLOAD']), lambda: scope, os.environ['REVIEW_KEY'])
