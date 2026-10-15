"""Exercise only the standard-library shared limiter in disposable Linux children."""

import json
import subprocess
import sys
import time

for operation, code in (
    ('memory', "allocation=bytearray(200*1024**2); print('UNEXPECTED_ALLOCATION',flush=True)"),
    ('cpu', 'while True:\n    pass\n'),
):
    source = ('from ai_intel.infrastructure.process_limits import bound_process_resources\n'
              'bound_process_resources(memory_bytes=100*1024**2,cpu_seconds=1)\n'
              "print('LIMIT_APPLIED',flush=True)\n" + code)
    start = time.monotonic()
    result = subprocess.run([sys.executable, '-c', source], capture_output=True, timeout=8, check=False)
    assert b'LIMIT_APPLIED' in result.stdout
    assert result.returncode != 0
    assert b'UNEXPECTED_ALLOCATION' not in result.stdout
    if operation == 'memory':
        assert b'MemoryError' in result.stderr or result.returncode < 0
    else:
        assert b'Traceback' not in result.stderr
    print(json.dumps({'kind': operation, 'python': sys.version.split()[0], 'exit': result.returncode,
                      'elapsed_seconds': time.monotonic()-start, 'stdout': result.stdout.decode(), 'stderr': result.stderr.decode()}))
