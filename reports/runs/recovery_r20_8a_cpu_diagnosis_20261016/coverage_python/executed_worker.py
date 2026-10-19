
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

from ai_intel.infrastructure import process_limits as limits
_diag('before_bound')
limits._WINDOWS_CPU_GUARD_CODE="\nimport ctypes,json,os,sys,time\n_api_start=time.monotonic()\n_native_dll=ctypes.WinDLL\ndef _diag(event, **fields):\n    print(json.dumps(dict(event=event,pid=os.getpid(),wall=time.monotonic()-_api_start,self_cpu=time.process_time(),**fields)),flush=True)\nclass _Function:\n    def __init__(self,name,function):\n        object.__setattr__(self,'name',name)\n        object.__setattr__(self,'function',function)\n    def __setattr__(self,name,value):\n        setattr(self.function,name,value)\n    def __call__(self,*args):\n        ctypes.set_last_error(0)\n        result=self.function(*args)\n        error=ctypes.get_last_error()\n        fields=dict(api=self.name,result=result,win32_error=error)\n        if self.name=='GetProcessTimes':\n            fields.update(target_handle=args[0],times=[arg._obj.value for arg in args[1:]])\n        if self.name in ('AssignProcessToJobObject','TerminateProcess','WaitForSingleObject','SetEvent','GetHandleInformation','CloseHandle'):\n            fields.update(arguments=[arg.value if hasattr(arg,'value') else arg if isinstance(arg,int) else str(type(arg)) for arg in args])\n        if self.name=='SetInformationJobObject':\n            limits=args[2]._obj\n            fields.update(flags=limits.basic.flags,process_time=limits.basic.process_time,memory=limits.process_memory)\n        _diag('api',**fields)\n        return result\nclass _Kernel:\n    def __init__(self,native): self.native=native\n    def __getattr__(self,name):\n        function=_Function(name,getattr(self.native,name))\n        setattr(self,name,function)\n        return function\nctypes.WinDLL=lambda *args,**kwargs:_Kernel(_native_dll(*args,**kwargs))\n_diag('entry',coverage_active='coverage' in sys.modules, executable=sys.executable,base_prefix=sys.base_prefix)\n"+limits._WINDOWS_CPU_GUARD_CODE
limits._WINDOWS_CPU_GUARD_CODE=limits._WINDOWS_CPU_GUARD_CODE.replace('    while True:\n',"    _diag('fault_window_start')\n    import time,os\n    time.sleep(0.4)\n    _diag('hard_exit')\n    os._exit(99)\n    while True:\n")
_original_popen=limits.subprocess.Popen
def _guard_popen(*args,**kwargs):
    kwargs['stdout']=open('D:\\wt\\r20-8a-diag\\codex\\r20-8a-cpu-guard-diagnosis\\reports\\runs\\recovery_r20_8a_cpu_diagnosis_20261016\\coverage_python\\guard.stdout.jsonl','wb',buffering=0)
    kwargs['stderr']=open('D:\\wt\\r20-8a-diag\\codex\\r20-8a-cpu-guard-diagnosis\\reports\\runs\\recovery_r20_8a_cpu_diagnosis_20261016\\coverage_python\\guard.stderr.log','wb',buffering=0)
    child=_original_popen(*args,**kwargs)
    _diag('guard_launched',guard_pid=child.pid)
    return child
limits.subprocess.Popen=_guard_popen
handle=limits.bound_process_resources(memory_bytes=100*1024**2,cpu_seconds=1)
limits.subprocess.Popen=_original_popen
_diag('after_bound')
import subprocess
leaf=subprocess.Popen([os.path.join(sys.base_prefix,'python.exe'),'-I','-S','-c','import time;time.sleep(10)'],creationflags=0x08000000)
print('TREE',os.getpid(),limits._WINDOWS_CPU_GUARDS[0].pid,leaf.pid,flush=True)
_diag('before_workload')
sys.setswitchinterval(60)
while time.process_time()<2.25:
    pass
print('UNSUPERVISED_RESULT',flush=True)
