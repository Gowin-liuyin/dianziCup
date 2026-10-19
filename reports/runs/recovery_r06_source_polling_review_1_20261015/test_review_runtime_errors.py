"""Task registration and failures remain observable without real source IO."""

import importlib
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from ai_intel.ingestion.source_polling import SourcePollingError


def runtime(monkeypatch,enabled):
    monkeypatch.setenv('DATABASE_URL','postgresql+psycopg://fixture@127.0.0.1:25432/test_fixture')
    monkeypatch.setenv('REDIS_URL','redis://127.0.0.1:26379/15')
    monkeypatch.setenv('SOURCE_POLLING_ENABLED','true' if enabled else 'false')
    return importlib.import_module('ai_intel.workers.runtime')


def test_registered_disabled_task_never_opens_pg(monkeypatch):
    module=runtime(monkeypatch,False)
    unexpected=MagicMock(side_effect=AssertionError('disabled task touched PG'))
    monkeypatch.setattr(module,'build_engine',unexpected)
    assert module.celery_app.tasks['ai_intel.sources.poll_due'].run()=={'state':'disabled','queued':0}
    unexpected.assert_not_called()


@pytest.mark.parametrize('error,expected,message',[(SQLAlchemyError('fixture database failure'),RuntimeError,'source polling database unavailable'),(SourcePollingError('fixture corrupt queue'),SourcePollingError,'fixture corrupt queue')])
def test_enabled_database_and_queue_errors_propagate_instead_of_zero(monkeypatch,error,expected,message):
    module=runtime(monkeypatch,True)
    engine=MagicMock()
    session=MagicMock()
    session.__enter__.return_value=session
    monkeypatch.setattr(module,'build_engine',lambda settings:engine)
    monkeypatch.setattr(module,'Session',lambda engine:session)
    enqueue=MagicMock(side_effect=error)
    monkeypatch.setattr(module,'enqueue_due_source_collections',enqueue)
    with pytest.raises(expected,match=message):
        module.celery_app.tasks['ai_intel.sources.poll_due'].run()
    engine.dispose.assert_called_once()
    assert enqueue.call_args.args[1].tenant_id is None
    assert enqueue.call_args.args[1].role.value=='system_admin'
    assert session.begin.return_value.__exit__.call_args.args[0] is type(error)


def test_poll_task_has_no_arbitrary_url_or_tenant_arguments(monkeypatch):
    module=runtime(monkeypatch,False)
    with pytest.raises(TypeError):
        module.celery_app.tasks['ai_intel.sources.poll_due'].run(url='https://example.invalid',tenant_id='attacker')
