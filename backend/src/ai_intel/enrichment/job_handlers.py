"""Register only the three fixed enrichment job types in the shared PG executor."""

from ai_intel.enrichment.job_service import (
    ENRICHMENT_PARENT_JOB_TYPE,
    ENRICHMENT_PUBLICATION_JOB_TYPE,
    ENRICHMENT_STEP_JOB_TYPE,
    EnrichmentJobService,
)
from ai_intel.workers.executor import JobHandler


def make_enrichment_job_handlers(service: EnrichmentJobService) -> dict[str, JobHandler]:
    return {
        ENRICHMENT_PARENT_JOB_TYPE: service.initialize,
        ENRICHMENT_STEP_JOB_TYPE: service.execute_step,
        ENRICHMENT_PUBLICATION_JOB_TYPE: service.publish,
    }
