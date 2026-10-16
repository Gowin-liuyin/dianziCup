"""认证的引用问答入口，历史读取不依赖外部模型当前是否可用。"""

from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import Response
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from ai_intel.answering.service import (
    GroundedQuestionService,
    QuestionFailure,
    read_grounded_answer,
)
from ai_intel.api.auth_routes import CSRF_HEADER_NAME, SESSION_COOKIE_NAME
from ai_intel.api.authentication import (
    AuthenticationSessionService,
    CsrfRejectionError,
    InvalidCredentialsError,
    SessionExpiredError,
)
from ai_intel.api.problems import problem_response
from ai_intel.api.question_contracts import QuestionAnswerResponse, QuestionRequest
from ai_intel.domain.access import (
    READ_PUBLIC,
    AccessScope,
    CrossTenantAccessError,
    PermissionDeniedError,
)
from ai_intel.infrastructure.models.generation import GenerationClient, GenerationLimits
from ai_intel.infrastructure.models.semantic import LocalSemanticModels
from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.retrieval.service import EventEvidenceRetriever


def build_question_service(
    engine: Engine | None, settings: ApplicationSettings
) -> GroundedQuestionService | None:
    if (
        engine is None
        or settings.generation_api_key is None
        or settings.semantic_model_cache_directory is None
    ):
        return None
    models = LocalSemanticModels(settings.semantic_model_cache_directory)
    client = GenerationClient(
        settings.generation_provider,
        settings.generation_model,
        settings.generation_api_key,
        limits=GenerationLimits(total_timeout_seconds=30.0, max_calls=1),
        dns_resolver=settings.dns_resolver,
    )
    return GroundedQuestionService(
        engine,
        EventEvidenceRetriever(engine, models, data_mode=settings.data_mode),
        client,
        data_mode=settings.data_mode,
    )


def build_question_router(
    service_provider: Callable[[], AuthenticationSessionService | None],
    engine: Engine | None,
    settings: ApplicationSettings,
) -> APIRouter:
    router = APIRouter()
    questions = build_question_service(engine, settings)

    def authenticate(request: Request, *, write: bool) -> AccessScope:
        token = request.cookies.get(SESSION_COOKIE_NAME, "")
        if not token:
            raise InvalidCredentialsError("missing session")
        authentication = service_provider()
        if authentication is None or engine is None:
            raise QuestionFailure("question_database_unavailable")
        if write:
            authentication.validate_write_request(
                token, request.headers.get(CSRF_HEADER_NAME, ""), request.headers.get("origin")
            )
        scope = authentication.build_access_scope(token)
        scope.requires(READ_PUBLIC)
        return scope

    def failure(request: Request, error: Exception) -> Response:
        if isinstance(error, (SessionExpiredError, InvalidCredentialsError)):
            return problem_response(request, 401, "session_expired", "session is not valid")
        if isinstance(error, CsrfRejectionError):
            return problem_response(request, 403, "csrf_rejected", "valid origin and CSRF required")
        if isinstance(error, PermissionDeniedError):
            return problem_response(
                request, 403, "permission_denied", "required permission missing"
            )
        if isinstance(error, CrossTenantAccessError):
            return problem_response(
                request, 404, "not_found", "requested resource is not available"
            )
        if isinstance(error, QuestionFailure):
            code = "answer_failed" if error.code == "answer_lease_expired" else error.code
            return problem_response(
                request, error.status, code, "question request could not be completed"
            )
        return problem_response(
            request, 503, "question_database_unavailable", "question database is unavailable"
        )

    @router.post("/questions", response_model=QuestionAnswerResponse)
    def ask_question(
        request: Request, payload: QuestionRequest
    ) -> QuestionAnswerResponse | Response:
        try:
            authenticate(request, write=True)
            if questions is None:
                raise QuestionFailure("question_models_not_configured")
            return questions.ask(
                payload,
                lambda: authenticate(request, write=False),
                request.headers.get("idempotency-key"),
                session_token=request.cookies.get(SESSION_COOKIE_NAME, ""),
            )
        except (
            SessionExpiredError,
            InvalidCredentialsError,
            CsrfRejectionError,
            PermissionDeniedError,
            CrossTenantAccessError,
            QuestionFailure,
            SQLAlchemyError,
            ValueError,
        ) as error:
            return failure(request, error)

    @router.get("/answers/{answer_id}", response_model=QuestionAnswerResponse)
    def get_answer(request: Request, answer_id: UUID) -> QuestionAnswerResponse | Response:
        try:
            scope = authenticate(request, write=False)
            if engine is None:
                raise QuestionFailure("question_database_unavailable")
            return read_grounded_answer(
                engine,
                scope,
                answer_id,
                session_token=request.cookies.get(SESSION_COOKIE_NAME, ""),
            )
        except (
            SessionExpiredError,
            InvalidCredentialsError,
            PermissionDeniedError,
            CrossTenantAccessError,
            QuestionFailure,
            SQLAlchemyError,
            ValueError,
        ) as error:
            return failure(request, error)

    return router
