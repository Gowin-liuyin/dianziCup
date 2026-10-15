"""Independent cleanup fault injection keeps primary failures and recovers admission."""

from pathlib import Path

import pytest

from ai_intel.infrastructure.models import semantic


@pytest.mark.parametrize("ready", [True, False])
def test_close_and_terminate_failures_still_kill_and_release(ready, monkeypatch, tmp_path: Path):
    events = []

    class Receiver:
        def poll(self, timeout):
            return ready

        def recv(self):
            return "ok", [[1.0] + [0.0] * 383]

        def close(self):
            events.append("receiver-close-error")
            raise OSError("SYNTHETIC_PRIVATE_CLEANUP")

    class Sender:
        def close(self):
            events.append("sender-closed")

    class Process:
        pid = None
        alive = False

        def start(self):
            self.pid = 4321
            self.alive = True

        def is_alive(self):
            return self.alive

        def terminate(self):
            events.append("terminate-error")
            raise OSError("SYNTHETIC_PRIVATE_TERMINATE")

        def kill(self):
            events.append("killed")
            self.alive = False

        def join(self, timeout):
            events.append("joined")

        def close(self):
            assert not self.alive
            events.append("process-closed")

    class Context:
        def Pipe(self, duplex):
            return Receiver(), Sender()

        def Process(self, **kwargs):
            return Process()

    monkeypatch.setattr(semantic.multiprocessing, "get_context", lambda _: Context())
    expected = semantic.SemanticRuntimeError if ready else semantic.SemanticTimeoutError
    with pytest.raises(expected) as captured:
        semantic.LocalSemanticModels(tmp_path).embed_query("private synthetic question")
    assert "SYNTHETIC_PRIVATE" not in str(captured.value)
    assert "killed" in events and "process-closed" in events
    assert not semantic._WORKER_LOCK.locked()
    if not ready:
        assert captured.value.__notes__ == ["local semantic worker cleanup was incomplete"]
