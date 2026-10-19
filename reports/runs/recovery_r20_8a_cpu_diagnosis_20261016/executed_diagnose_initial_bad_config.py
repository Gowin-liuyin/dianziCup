"""Run bounded worker samples, preserving exact and instrumented cases separately."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from observe_processes import observe

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
PYTHON = str(ROOT / "backend/.venv/Scripts/python.exe")
BACKEND = ROOT / "backend"

NATIVE_WORKLOADS = {
    "short": "print('RESULT',sum(range(100_000)),flush=True)\n",
    "python": "sys.setswitchinterval(60)\nwhile time.process_time()<2.25:\n    pass\n",
    "idle": "ctypes.PyDLL('kernel32').Sleep(2000)\n",
    "native": "import hashlib\nhashlib.pbkdf2_hmac('sha256',b'a',b'b',100_000_000)\n",
}

DIAGNOSTIC_PREFIX = r'''
import ctypes,json,os,sys,time
_api_start=time.monotonic()
_native_dll=ctypes.WinDLL
def _diag(event, **fields):
    print(json.dumps(dict(event=event,pid=os.getpid(),wall=time.monotonic()-_api_start,self_cpu=time.process_time(),**fields)),flush=True)
class _Function:
    def __init__(self,name,function):
        object.__setattr__(self,'name',name)
        object.__setattr__(self,'function',function)
    def __setattr__(self,name,value):
        setattr(self.function,name,value)
    def __call__(self,*args):
        ctypes.set_last_error(0)
        result=self.function(*args)
        error=ctypes.get_last_error()
        fields=dict(api=self.name,result=result,win32_error=error)
        if self.name=='GetProcessTimes':
            fields.update(target_handle=args[0],times=[arg._obj.value for arg in args[1:]])
        if self.name in ('AssignProcessToJobObject','TerminateProcess','WaitForSingleObject','SetEvent','GetHandleInformation','CloseHandle'):
            fields.update(arguments=[arg.value if hasattr(arg,'value') else arg if isinstance(arg,int) else str(type(arg)) for arg in args])
        if self.name=='SetInformationJobObject':
            limits=args[2]._obj
            fields.update(flags=limits.basic.flags,process_time=limits.basic.process_time,memory=limits.process_memory)
        _diag('api',**fields)
        return result
class _Kernel:
    def __init__(self,native): self.native=native
    def __getattr__(self,name):
        function=_Function(name,getattr(self.native,name))
        setattr(self,name,function)
        return function
ctypes.WinDLL=lambda *args,**kwargs:_Kernel(_native_dll(*args,**kwargs))
_diag('entry',coverage_active='coverage' in sys.modules, executable=sys.executable,base_prefix=sys.base_prefix)
'''


def instrumented_code(workload: str, *, fault: bool, directory: Path) -> str:
    guard_file = directory / "guard.stdout.jsonl"
    guard_error = directory / "guard.stderr.log"
    code = DIAGNOSTIC_PREFIX + "\nfrom ai_intel.infrastructure import process_limits as limits\n"
    code += "_diag('before_bound')\n"
    code += f"limits._WINDOWS_CPU_GUARD_CODE={DIAGNOSTIC_PREFIX!r}+limits._WINDOWS_CPU_GUARD_CODE\n"
    if fault:
        code += (
            "limits._WINDOWS_CPU_GUARD_CODE=limits._WINDOWS_CPU_GUARD_CODE.replace("
            "'    while True:\\n',\"    _diag('fault_window_start')\\n    import time,os\\n    time.sleep(0.4)\\n    _diag('hard_exit')\\n    os._exit(99)\\n    while True:\\n\")\n"
        )
    code += (
        "_original_popen=limits.subprocess.Popen\n"
        "def _guard_popen(*args,**kwargs):\n"
        f"    kwargs['stdout']=open({str(guard_file)!r},'wb',buffering=0)\n"
        f"    kwargs['stderr']=open({str(guard_error)!r},'wb',buffering=0)\n"
        "    child=_original_popen(*args,**kwargs)\n"
        "    _diag('guard_launched',guard_pid=child.pid)\n"
        "    return child\n"
        "limits.subprocess.Popen=_guard_popen\n"
        "handle=limits.bound_process_resources(memory_bytes=100*1024**2,cpu_seconds=1)\n"
        "limits.subprocess.Popen=_original_popen\n"
        "_diag('after_bound')\n"
    )
    if fault:
        code += (
            "import subprocess\n"
            "leaf=subprocess.Popen([os.path.join(sys.base_prefix,'python.exe'),'-I','-S','-c','import time;time.sleep(10)'],creationflags=0x08000000)\n"
            "print('TREE',os.getpid(),limits._WINDOWS_CPU_GUARDS[0].pid,leaf.pid,flush=True)\n"
            "_diag('before_workload')\n"
        )
    code += workload
    if fault:
        code += "print('UNSUPERVISED_RESULT',flush=True)\n"
    return code


def environment(coverage: bool) -> dict[str, str]:
    result = dict(os.environ)
    for key in tuple(result):
        if key.startswith(("COV_CORE_", "COVERAGE_")):
            result.pop(key)
    result.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    if coverage:
        result.update(COV_CORE_SOURCE=str(BACKEND / "src/ai_intel"), COV_CORE_CONFIG="os.devnull",
                      COV_CORE_DATAFILE=str(RUN / "diagnostic.coverage"))
    return result


def originals() -> None:
    nodes = ["tests/unit/test_r20_native_cpu_guard.py::test_short_cpu_task_keeps_its_result"]
    nodes += [f"tests/unit/test_r20_native_cpu_guard.py::test_guard_hard_exit_after_readiness_terminates_worker_tree[{name}]"
              for name in ("python-gil-held", "native-gil-held-idle", "native-cpu")]
    command = [PYTHON, "-B", "-m", "pytest", *nodes, "-v",
               "--junitxml=" + str(RUN / "original_four.xml"),
               "--cov-report=json:" + str(RUN / "original_four.coverage.json"),
               "-o", "cache_dir=" + str(RUN / "pytest_cache"),
               "--basetemp=" + str(RUN / "pytest_temp")]
    observe("original_four", command, cwd=BACKEND, run=RUN, environment=environment(False), timeout=30)


def instrumented(mode: str) -> None:
    coverage = mode == "coverage"
    for name, workload in NATIVE_WORKLOADS.items():
        sample = f"{mode}_{name}"
        directory = RUN / sample
        directory.mkdir(exist_ok=True)
        code = instrumented_code(workload, fault=name != "short", directory=directory)
        (directory / "executed_worker.py").write_text(code, encoding="utf-8")
        observe(sample, [PYTHON, "-c", code], cwd=BACKEND, run=RUN,
                environment=environment(coverage), timeout=8)


if __name__ == "__main__":
    if sys.argv[1] == "originals":
        originals()
    else:
        instrumented(sys.argv[1])
