"""故意触发原认证测试失败，在内存扫描pytest失败文本后才脱敏写盘。"""
from pathlib import Path
import contextlib, io, json, os, sys
import pytest
LOG=Path(r'D:\dianzi\reports\runs\recovery_r02_persistence_review_1_20261015')
WT=Path(r'C:\Users\yinha\.codex\worktrees\recovery-r02-review\dianzi')
known={}
class FailureInjector:
    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_call(self,item):
        previous=sys.gettrace()
        def trace(frame,event,arg):
            if frame.f_code.co_name=='test_session_hash_only_is_stored' and event=='return':
                values=frame.f_locals
                known['token']=values['token']
                known['session_hash']=values['record'].session_id
                known['csrf_token']=values['record'].csrf_token
                known['password']=values['pg_auth'].password
                sys.settrace(None)
                raise AssertionError('controlled reviewer failure in original authentication test')
            return trace
        sys.settrace(trace)
        try:
            yield
        finally:
            sys.settrace(previous)
stdout=io.StringIO()
stderr=io.StringIO()
with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
    code=pytest.main(['tests/unit','tests/integration/test_r02_auth_state.py::test_session_hash_only_is_stored','--showlocals','-p','no:cacheprovider','-q'],plugins=[FailureInjector()])
output=stdout.getvalue()+stderr.getvalue()
observed={}
for name,value in known.items():
    fragments=[value[i:i+8] for i in range(max(0,len(value)-7))]
    observed[name]={'full_value_exposed':value in output,'any_eight_char_fragment_exposed':any(fragment in output for fragment in fragments)}
for value in sorted(set(known.values()),key=len,reverse=True):
    output=output.replace(value,'[redacted authentication test value]')
    for i in range(max(0,len(value)-7)):
        output=output.replace(value[i:i+8],'[redacted authentication fragment]')
from urllib.parse import urlsplit,unquote
url=os.environ['TEST_DATABASE_URL']
password=unquote(urlsplit(url).password or '')
for value in (url,password):
    output=output.replace(value,'[redacted connection value]')
    for i in range(max(0,len(value)-7)):
        output=output.replace(value[i:i+8],'[redacted connection fragment]')
(LOG/'credential_failure_sanitized.log').write_text(output,encoding='utf-8')
result={'controlled_failure_exit':int(code),'native_showlocals_retained':True,'native_junit_not_written':True,'original_test_path':str(WT/'backend/tests/integration/test_r02_auth_state.py'),'secrets_scanned_beforewrite':True,'observed':observed}
(LOG/'credential_failure.observed.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
