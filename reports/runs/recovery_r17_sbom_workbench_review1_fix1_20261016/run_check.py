"""Record independent fix verification without changing product sources."""
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
RUN=Path(__file__).resolve().parent
ZONE=timezone(timedelta(hours=8))
def main():
    sys.stdout.reconfigure(encoding="utf-8",errors="replace")
    name,relative,*command=sys.argv[1:]
    started=datetime.now(ZONE).isoformat(timespec="seconds")
    try:
        result=subprocess.run(command,cwd=ROOT/relative,capture_output=True,timeout=600)
        output,code=result.stdout+result.stderr,result.returncode
    except subprocess.TimeoutExpired as failure:
        output,code=(failure.stdout or b"")+(failure.stderr or b""),124
    (RUN/f"{name}.log").write_bytes(output)
    receipt={"command":command,"cwd":str(ROOT/relative),"started_at":started,"finished_at":datetime.now(ZONE).isoformat(timespec="seconds"),"exit_code":code,"log":f"{name}.log","code_target":"5587deb124f06b9aa14fb7feb22cdc9493ae4883","source_sha":"18d05f1c5842ed7a57f3be9f0351ede4af0b018a"}
    (RUN/f"{name}.command.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps(receipt,ensure_ascii=False));print(output.decode("utf-8",errors="replace")[-2400:]);return code
if __name__=="__main__":raise SystemExit(main())
