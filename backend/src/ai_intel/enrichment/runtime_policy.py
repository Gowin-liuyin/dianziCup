"""Build bounded generation clients from server configuration without external IO."""

from sqlalchemy.engine import Engine

from ai_intel.enrichment.job_contracts import EnrichmentExecutionPolicy
from ai_intel.enrichment.job_service import EnrichmentJobService
from ai_intel.infrastructure.content_storage_factory import build_content_storage
from ai_intel.infrastructure.models.generation import GenerationClient, GenerationLimits
from ai_intel.infrastructure.settings import ApplicationSettings


def build_enrichment_execution_policy(settings: ApplicationSettings) -> EnrichmentExecutionPolicy:
    """The persisted policy excludes credentials and is independent of HTTP request fields."""
    enabled = settings.enrichment_generation_enabled
    return EnrichmentExecutionPolicy(
        generation_enabled=enabled,
        generation_provider=settings.generation_provider if enabled else None,
        approved_model=settings.generation_model if enabled else None,
        private_egress_granted=settings.enrichment_private_egress_granted,
        aggregate_enabled=settings.enrichment_aggregate_enabled,
        data_mode=settings.data_mode,
    )


def build_enrichment_generation_client(settings: ApplicationSettings) -> GenerationClient | None:
    """Each child gets a fresh one-call client whose deadline fits the existing worker limit."""
    if not settings.enrichment_generation_enabled or settings.generation_api_key is None:
        return None
    return GenerationClient(
        settings.generation_provider,
        settings.generation_model,
        settings.generation_api_key,
        limits=GenerationLimits(
            total_timeout_seconds=20.0,
            max_calls=1,
            max_concurrent_requests=1,
        ),
        dns_resolver=settings.dns_resolver,
    )


def build_enrichment_job_service(
    engine: Engine | None,
    settings: ApplicationSettings,
) -> EnrichmentJobService | None:
    """API and worker share policy and factories; import or enqueue makes no paid call."""
    if engine is None:
        return None
    return EnrichmentJobService(
        engine,
        build_content_storage(settings),
        execution_policy=lambda: build_enrichment_execution_policy(settings),
        generation_client_factory=lambda: build_enrichment_generation_client(settings),
    )
