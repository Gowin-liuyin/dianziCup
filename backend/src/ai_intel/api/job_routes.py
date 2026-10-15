"""One default job reader exposes only public-admin sources or authorized workflow jobs."""

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import Response
from sqlalchemy import or_, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ai_intel.api.auth_routes import SESSION_COOKIE_NAME
from ai_intel.api.auth_state import lock_authenticated_scope
from ai_intel.api.authentication import (
    AuthenticationSessionService,
    InvalidCredentialsError,
    SessionExpiredError,
)
from ai_intel.api.problems import problem_response
from ai_intel.api.source_routes import SourceJobResponse
from ai_intel.domain.access import READ_PUBLIC, CrossTenantAccessError, PermissionDeniedError, Role
from ai_intel.enrichment.job_models import enrichment_job_steps, enrichment_workflows
from ai_intel.enrichment.job_service import EnrichmentJobService, EnrichmentWorkflowError
from ai_intel.ingestion.source_jobs import SOURCE_JOB_TYPE
from ai_intel.knowledge.models import job_runs


def build_job_router(
    service_provider: Callable[[], AuthenticationSessionService | None],
    engine: Engine | None,
    enrichment: EnrichmentJobService | None,
) -> APIRouter:
    """Workflow owners gain scoped reads; the legacy source-administration denial remains 403."""
    router = APIRouter()

    @router.get("/jobs/{job_id}", response_model=SourceJobResponse)
    def read_job(request: Request, job_id: UUID) -> SourceJobResponse | Response:
        token = request.cookies.get(SESSION_COOKIE_NAME, "")
        if not token:
            return problem_response(request, 401, "unauthenticated", "session is not valid")
        authentication = service_provider()
        if authentication is None or engine is None:
            return problem_response(
                request, 503, "jobs_unavailable", "job database is unavailable", True
            )
        try:
            initial = authentication.build_access_scope(token)
            initial.requires(READ_PUBLIC)
            with Session(engine) as session, session.begin():
                scope = lock_authenticated_scope(session.connection(), token, datetime.now(UTC))
                if scope != initial:
                    raise PermissionDeniedError("job authorization changed")
                workflow = session.scalar(
                    select(enrichment_workflows.c.workflow_id)
                    .outerjoin(enrichment_job_steps)
                    .where(
                        enrichment_workflows.c.actor_user_id == scope.user_id,
                        or_(
                            enrichment_workflows.c.parent_job_id == str(job_id),
                            enrichment_job_steps.c.job_id == str(job_id),
                        ),
                    )
                    .limit(1)
                )
                if workflow is not None and enrichment is not None:
                    enrichment.read_workflow(
                        session,
                        scope,
                        UUID(workflow),
                        actor_session_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
                        at=datetime.now(UTC),
                    )
                    row = (
                        session.execute(select(job_runs).where(job_runs.c.job_id == str(job_id)))
                        .mappings()
                        .first()
                    )
                elif scope.role == Role.SYSTEM_ADMIN and scope.tenant_id is None:
                    row = (
                        session.execute(
                            select(job_runs).where(
                                job_runs.c.job_id == str(job_id),
                                job_runs.c.job_type == SOURCE_JOB_TYPE,
                                job_runs.c.tenant_id.is_(None),
                            )
                        )
                        .mappings()
                        .first()
                    )
                else:
                    row = None
                if row is None:
                    if scope.role != Role.SYSTEM_ADMIN or scope.tenant_id is not None:
                        return problem_response(
                            request, 403, "permission_denied", "job access is not permitted"
                        )
                    return problem_response(request, 404, "not_found", "job is not available")
                return SourceJobResponse.model_validate(dict(row))
        except (InvalidCredentialsError, SessionExpiredError):
            return problem_response(request, 401, "unauthenticated", "session is not valid")
        except PermissionDeniedError:
            return problem_response(
                request, 403, "permission_denied", "required permission missing"
            )
        except CrossTenantAccessError:
            if initial.role != Role.SYSTEM_ADMIN or initial.tenant_id is not None:
                return problem_response(
                    request, 403, "permission_denied", "job access is not permitted"
                )
            return problem_response(request, 404, "not_found", "job is not available")
        except EnrichmentWorkflowError as error:
            if error.status == 404:
                if initial.role != Role.SYSTEM_ADMIN or initial.tenant_id is not None:
                    return problem_response(
                        request, 403, "permission_denied", "job access is not permitted"
                    )
                return problem_response(request, 404, "not_found", "job is not available")
            return problem_response(request, 409, "workflow_changed", "workflow state changed")
        except (SQLAlchemyError, ValueError):
            return problem_response(
                request, 503, "jobs_unavailable", "job database is unavailable", True
            )

    return router
