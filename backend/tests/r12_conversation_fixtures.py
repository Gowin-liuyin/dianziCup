"""Owned real PG schema and explicit synthetic workflow receipts, without model IO."""

from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, text, update
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from ai_intel.answering.conversation_context import ConversationContextService
from ai_intel.answering.conversation_contracts import ConversationTurn
from ai_intel.answering.conversation_models import qa_conversation_turns, qa_conversations
from ai_intel.api.auth_state import PgAuthenticationStateStore
from ai_intel.api.authentication import AuthenticationSessionService, DatabaseUserDirectory
from ai_intel.api.question_contracts import QuestionAnswerResponse
from ai_intel.domain.access import AccessScope, Role
from ai_intel.domain.enums import FreshnessStatus
from ai_intel.infrastructure.database import run_migrations
from ai_intel.knowledge.models import metadata
from ai_intel.retrieval.persistence_models import grounded_answers


@pytest.fixture
def conversation_database(isolated_test_database_url: str) -> Iterator[Engine]:
    url = make_url(isolated_test_database_url)
    assert url.database == "test_dianzi_r12_context_20261016"
    schema = "test_r12_context_" + uuid4().hex
    base = create_engine(url, connect_args={"connect_timeout": 3})
    with base.begin() as connection:
        connection.execute(CreateSchema(schema))
    migration_url = url.update_query_dict(
        {"options": f"-c search_path={schema} -c statement_timeout=15000 -c lock_timeout=3000"}
    )
    run_migrations(migration_url.render_as_string(hide_password=False))
    runtime = url.update_query_dict(
        {
            "options": f"-c search_path={schema},public "
            "-c statement_timeout=15000 -c lock_timeout=3000"
        }
    )
    engine = create_engine(runtime, connect_args={"connect_timeout": 3})
    with engine.begin() as connection:
        assert connection.scalar(text("SELECT current_schema()")) == schema
        metadata.create_all(connection, tables=[qa_conversations, qa_conversation_turns])
    try:
        yield engine
    finally:
        engine.dispose()
        assert schema.startswith("test_r12_context_") and schema.isidentifier()
        with base.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        base.dispose()
        print("owned_context_schema_removed:" + schema)


@pytest.fixture
def context_identity(conversation_database, register_sensitive_failure_value):
    authentication = AuthenticationSessionService(
        DatabaseUserDirectory(conversation_database),
        ("http://localhost:5173",),
        False,
        state_store=PgAuthenticationStateStore(conversation_database),
    )

    def login(*, tenant="tenant-a", role=Role.ANALYST):
        password = "synthetic-context-password-" + uuid4().hex
        register_sensitive_failure_value(SecretStr(password))
        username = "synthetic-context-user-" + uuid4().hex
        authentication.create_precreated_user(username, password, tenant, role)
        token, record = authentication.login(
            username, password, "http://localhost:5173", uuid4().hex
        )
        register_sensitive_failure_value(SecretStr(token))
        register_sensitive_failure_value(SecretStr(record.csrf_token))
        return authentication.build_access_scope(token), token

    scope, token = login()
    return conversation_database, authentication, scope, token, login


def record_synthetic_completion(
    service: ConversationContextService,
    engine: Engine,
    scope: AccessScope,
    token: str,
    turn: ConversationTurn,
) -> ConversationTurn:
    """Test only: a marked receipt isolates workflow ack, not source-supported model answers."""
    now = datetime.now(UTC)
    answer = QuestionAnswerResponse(
        answer_id=turn.answer_id,
        answer_text="Synthetic workflow receipt; no generated factual answer.",
        claims=(),
        citations=(),
        limitations=("synthetic workflow only",),
        freshness=FreshnessStatus.UNKNOWN,
        data_mode="fixture",
        started_at=turn.context.requested_at,
        completed_at=now,
        latency_milliseconds=0,
    )
    with Session(engine) as session, session.begin():
        service._authenticate(session, scope, token)
        service._conversation(session, scope, turn.conversation_id)
        session.execute(
            update(grounded_answers)
            .where(grounded_answers.c.answer_id == str(turn.answer_id))
            .values(response=answer.model_dump(mode="json"))
        )
        return service.acknowledge_completed_turn(
            session, scope, turn.turn_id, reservation_id=turn.reservation_id, session_token=token
        )
