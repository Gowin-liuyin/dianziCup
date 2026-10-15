from datetime import UTC,datetime
from ai_intel.infrastructure.network import FetchResult
from ai_intel.ingestion.source_jobs import _http_failure
from ai_intel.workers.executor import JobExecutionError

def test_fifty_year_boundary_compares_full_date():
    now = datetime(2026,10,15,12,34,56,tzinfo=UTC)
    response = FetchResult('https://api.github.com',429,'application/json',b'',redacted_headers={'Retry-After':'Saturday, 16-Oct-76 00:00:00 GMT'})
    try:
        _http_failure(response,clock=lambda:now)
    except JobExecutionError as failure:
        assert failure.retry_after_seconds == 7 and not failure.blocked
    else:
        raise AssertionError('429 must not succeed')
