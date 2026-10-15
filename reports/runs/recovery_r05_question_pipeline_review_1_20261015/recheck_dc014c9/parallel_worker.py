"""Synthetic wire child process; private PG URL/session passed only through environment."""
import json
import os
import sys
from pydantic import SecretStr
from sqlalchemy import create_engine
from test_r05_vector_persistence import FixtureSemanticModels
from test_r05_question_api_pg import FixtureGenerationWire
from ai_intel.answering.service import GroundedQuestionService, QuestionFailure
from ai_intel.api.authentication import AuthenticationSessionService, DatabaseUserDirectory
from ai_intel.api.auth_state import PgAuthenticationStateStore
from ai_intel.api.question_contracts import QuestionRequest
from ai_intel.infrastructure.models.generation import GenerationClient, GenerationLimits
from ai_intel.retrieval.service import EventEvidenceRetriever
engine = create_engine(os.environ['REVIEW_ISOLATED_DATABASE_URL'])
auth = AuthenticationSessionService(DatabaseUserDirectory(engine), ('http://localhost:5173',), False, state_store=PgAuthenticationStateStore(engine))
client = GenerationClient('deepseek_openai', 'deepseek-flash', SecretStr('review-recheck-explicit-synthetic-credential'), limits=GenerationLimits(total_timeout_seconds=30.0, max_calls=1))
wire = FixtureGenerationWire()
def simulated_post(url, body, *, protocol_headers, deadline):
    if not wire.calls:
        if sys.argv[1] == 'crash':
            os._exit(73)
        if sys.argv[1] == 'block':
            print('SIMULATED_WIRE_REACHED', flush=True)
            sys.stdin.readline()
    return wire.respond(url, body)
client._gateway.post_json = simulated_post
service = GroundedQuestionService(engine, EventEvidenceRetriever(engine, FixtureSemanticModels()), client, data_mode='fixture')
token = os.environ['REVIEW_SESSION_TOKEN']
try:
    answer = service.ask(QuestionRequest.model_validate_json(os.environ['REVIEW_PAYLOAD']), lambda: auth.build_access_scope(token), os.environ['REVIEW_KEY'], session_token=token)
    status = answer.kind
except QuestionFailure as error:
    status = error.code
print(json.dumps({'status': status, 'calls': len(wire.calls)}), flush=True)
engine.dispose()
