"""The investigation publisher and worker must name the same queue."""

from pathlib import Path

from ai_intel.workers.investigation import INVESTIGATION_QUEUE


def test_default_publisher_uses_the_investigation_queue() -> None:
    runtime = Path(__file__).parents[2] / "src/ai_intel/workers/runtime.py"
    source = runtime.read_text(encoding="utf-8")
    assert INVESTIGATION_QUEUE == "ai_intel_investigations"
    assert f'queue="{INVESTIGATION_QUEUE}"' in source
    assert 'task_default_queue="ai_intel"' in source
