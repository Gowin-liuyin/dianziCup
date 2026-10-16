"""Trusted runtime factories keep credentials and checkpoint configuration outside jobs."""

from __future__ import annotations

from sqlalchemy.engine import Engine

from ai_intel.api.actor_references import ActorReference
from ai_intel.api.credentials import AuthenticatedCredential
from ai_intel.infrastructure.models.generation import GenerationClient, GenerationLimits
from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.investigation.workflow_service import InvestigationWorkflowService

CHECKPOINT_SCHEMA = "dianzi_investigation_checkpoints"


def build_investigation_service(
    engine: Engine,
    settings: ApplicationSettings,
    actor: AuthenticatedCredential | ActorReference,
    *,
    checkpoint_schema: str = CHECKPOINT_SCHEMA,
) -> InvestigationWorkflowService:
    """Use the connected PG dependency and configured model; missing models stay explicit."""
    connection_string = engine.url.set(drivername="postgresql").render_as_string(
        hide_password=False
    )
    factory = None
    provider = None
    version = None
    if settings.generation_api_key is not None:

        def configured_model(limits: GenerationLimits) -> GenerationClient:
            if settings.generation_api_key is None:
                raise RuntimeError("investigation model not configured")
            return GenerationClient(
                settings.generation_provider,
                settings.generation_model,
                settings.generation_api_key,
                limits=limits,
                dns_resolver=settings.dns_resolver,
            )

        factory = configured_model
        provider = settings.generation_provider
        version = settings.generation_model
    return InvestigationWorkflowService(
        engine,
        actor,
        connection_string,
        checkpoint_schema,
        data_mode=settings.data_mode,
        model_factory=factory,
        model_provider=provider,
        model_version=version,
    )
