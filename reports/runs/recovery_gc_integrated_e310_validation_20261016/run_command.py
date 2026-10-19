"""Record isolated validation commands without environment values or credentials."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
ZONE = dt.timezone(dt.timedelta(hours=8))


def record(label, argv, cwd=ROOT, env=None):
    target = RUN / (label + '.command.json')
    if target.exists():
        raise ValueError('label already used')
    receipt = dict(label=label, argv=[str(x) for x in argv], cwd=str(cwd),
        started_at=dt.datetime.now(ZONE).isoformat(),
        code_sha=subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
        runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    target.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    environment = env or os.environ.copy()
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    result = subprocess.run([str(x) for x in argv], cwd=cwd, env=environment,
        capture_output=True, encoding='utf-8', errors='replace')
    for suffix, output in [('stdout',result.stdout),('stderr',result.stderr)]:
        for key in ['TEST_DATABASE_URL','DATABASE_URL','TEST_REDIS_URL']:
            value = environment.get(key,'')
            if value:
                output = output.replace(value, '[redacted test connection]')
        (RUN / (label+'.'+suffix+'.log')).write_text(output, encoding='utf-8')
    receipt.update(ended_at=dt.datetime.now(ZONE).isoformat(), exit_code=result.returncode)
    target.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(dict(label=label,exit_code=result.returncode)), flush=True)
    return result.returncode


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--cwd',default=str(ROOT))
    parser.add_argument('label')
    parser.add_argument('argv',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    argv=args.argv[1:] if args.argv[:1]==['--'] else args.argv
    raise SystemExit(record(args.label,argv,Path(args.cwd)))
