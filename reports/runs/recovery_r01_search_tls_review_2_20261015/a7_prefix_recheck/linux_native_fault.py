import base64,json,os,pathlib,subprocess,re,xml.etree.ElementTree as ET,datetime
private=pathlib.Path("/tmp/dianzi-r01-tls-prefix-review2-20261015")
values=json.loads((private/"connection.json").read_text())["environment"]
assert json.loads(values["DIANZI_DOCKER_COMMAND_JSON"]) == ["docker"]
assert len(values)==13
environment=dict(os.environ,**values,PYTHONUTF8="1",PYTEST_ADDOPTS="",
    PYTHONPATH="/mnt/d/dianzi/reports/runs/recovery_r01_search_tls_review_2_20261015/a7_prefix_recheck/native_plugin:/mnt/c/Users/yinha/.codex/worktrees/recovery-r01-tls-prefix-recheck/dianzi",
    PATH="/tmp/dianzi-r01-tls-prefix-runtime-20261015/bin:"+os.environ["PATH"])
command=["/tmp/dianzi-r01-tls-prefix-runtime-20261015/venv/bin/python","-m","pytest","-p","independent_memory_junit",
    "tests/integration/test_r01_search_tls_live.py","-k","fault","--no-cov","--showlocals",
    "--junitxml=review-native.xml","-q"]
started=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec="seconds")
result=subprocess.run(command,cwd="/mnt/c/Users/yinha/.codex/worktrees/recovery-r01-tls-prefix-recheck/dianzi/backend",env=environment,
    capture_output=True,text=True,timeout=240)
lines=result.stdout.splitlines()
xml=next(base64.b64decode(line.split("=",1)[1]).decode() for line in lines if line.startswith("REVIEW_MEMORY_JUNIT="))
stdout="\n".join(line for line in lines if not line.startswith(("REVIEW_MEMORY_JUNIT=","REVIEW_MEMORY_VALUES=")))
secret=values["TEST_SEARCH_TLS_PASSWORD"]
def leaked(text):
    return {"full":secret in text,"eight_character_fragment":any(secret[i:i+8] in text for i in range(len(secret)-7))}
def redact(text):
    text=text.replace(secret,"[review credential redacted]")
    return re.sub("|".join(re.escape(secret[i:i+8]) for i in range(len(secret)-7)),"[review fragment redacted]",text)
root=ET.fromstring(xml)
counts={key:sum(int(s.get(key,"0")) for s in root.iter("testsuite")) for key in ("tests","failures","errors","skipped")}
output=pathlib.Path("/mnt/d/dianzi/reports/runs/recovery_r01_search_tls_review_2_20261015/a7_prefix_recheck")
(output/"fault_native.log").write_text(redact(stdout+result.stderr))
(output/"fault_native.xml").write_text(redact(xml))
receipt={"command":command,"cwd":"/mnt/c/Users/yinha/.codex/worktrees/recovery-r01-tls-prefix-recheck/dianzi/backend","start":started,
    "end":datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec="seconds"),
    "source_sha":"a7c0a4aab37b3cf1916efb3cb480f5db148ead44","exit_code":result.returncode,"counts":counts,
    "prepare_values_used_without_replacing_docker_json":True,"exported_value_count":len(values),
    "pre_outer_redaction_stdout":leaked(stdout),"pre_outer_redaction_junit":leaked(xml),
    "pre_outer_redaction_stderr":leaked(result.stderr),"raw_junit_memory_only":True,
    "raw_junit_path_exists":pathlib.Path("/mnt/c/Users/yinha/.codex/worktrees/recovery-r01-tls-prefix-recheck/dianzi/backend/review-native.xml").exists()}
(output/"fault_native.json").write_text(json.dumps(receipt,indent=2)+"\n")
print(json.dumps(receipt))
raise SystemExit(result.returncode)
