"""Four final single-worker boundaries; no retry loop or changed product limit."""

from __future__ import annotations

from diagnose import BACKEND, DIAGNOSTIC_PREFIX, NATIVE_WORKLOADS, PYTHON, ROOT, RUN, environment, instrumented_code
from observe_processes import observe


def measured(name: str, workload: str, *, fault: bool, coverage: bool, cpu_before_bound: float | None = None):
    directory = RUN / name
    directory.mkdir(exist_ok=True)
    code = instrumented_code(workload, fault=fault, directory=directory)
    if cpu_before_bound is not None:
        code = code.replace("handle=limits.bound_process_resources(",
                            f"while time.process_time()<{cpu_before_bound!r}: pass\n"
                            "_diag('controlled_cpu_before_bound')\nhandle=limits.bound_process_resources(")
    (directory / "executed_worker.py").write_text(code, encoding="utf-8")
    observe(name, [PYTHON, "-c", code], cwd=BACKEND, run=RUN, environment=environment(coverage), timeout=8)


if __name__ == "__main__":
    measured("normal_poll_coverage", NATIVE_WORKLOADS["native"], fault=False, coverage=True)
    measured("controlled_initial_exhausted", NATIVE_WORKLOADS["python"], fault=True, coverage=False, cpu_before_bound=1.05)
    measured("controlled_idle_near_budget", NATIVE_WORKLOADS["idle"], fault=True, coverage=False, cpu_before_bound=0.96)
    code = (
        "from pathlib import Path\n"
        "from ai_intel.ingestion.parsing.pdf_text import parse_pdf_text_layer\n"
        f"source=Path({str(ROOT / 'docs/references/competition_brief.pdf')!r})\n"
        "result=parse_pdf_text_layer(source.read_bytes())\n"
        "print('PDF_RESULT',result.status,len(result.blocks),sorted({b.page_number for b in result.blocks}),flush=True)\n"
        "assert result.status=='parsed' and {b.page_number for b in result.blocks}=={1,2,3,4}\n"
    )
    (RUN / "executed_pdf_parent.py").write_text(code, encoding="utf-8")
    observe("real_pdf_parent", [PYTHON, "-c", code], cwd=BACKEND, run=RUN,
            environment=environment(False), timeout=8)
