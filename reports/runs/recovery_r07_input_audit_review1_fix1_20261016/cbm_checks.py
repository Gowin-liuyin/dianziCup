"""Fresh isolated CBM index is review evidence and never a runtime source of truth."""

import json
import subprocess

from checks import ROOT, RUN, now

PREFIX = ['wsl', '-d', 'Ubuntu-22.04', '-u', 'root', '--exec', '/usr/bin/env', 'CBM_CACHE_DIR=/tmp/dianzi-cbm-r07-audit-review1-fix1-20261016', '/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp', 'cli', '--json']


def execute(label, arguments):
    started = now()
    command = PREFIX + arguments
    result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=360)
    (RUN / (label + '.log')).write_bytes(result.stderr)
    (RUN / (label + '.json')).write_bytes(result.stdout)
    (RUN / (label + '_receipt.json')).write_bytes(json.dumps({'argv': command, 'cwd': str(ROOT), 'started_at': started, 'ended_at': now(), 'exit_code': result.returncode}, indent=2).encode())
    print(json.dumps({'label': label, 'exit_code': result.returncode}), flush=True)
    return result.returncode


if __name__ == '__main__':
    import sys
    raise SystemExit(execute(sys.argv[1], sys.argv[2:]))
