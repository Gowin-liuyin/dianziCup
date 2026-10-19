"""Verify owned segment 4 before asking its supervisor to stop normally."""

import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path('/mnt/d/dianzi/reports/runs/recovery_gb_controlled_collection_20261015')
OLD = Path('/mnt/d/dianzi/reports/runs/recovery_r04_minio_segment4_20261015')
GROUP = Path('/sys/fs/cgroup/dianzi-r01-20261014/minio-server-20261015')
assert not (OLD / 'service_end.json').exists()
receipt = json.loads((OLD / 'service_start.json').read_text())
assert receipt['supervisor_pid'] == 28048 and receipt['child_pid'] == 28049
supervisor_command = Path('/proc/28048/cmdline').read_bytes().replace(b'\0', b' ').decode().strip()
child_command = Path('/proc/28049/cmdline').read_bytes().replace(b'\0', b' ').decode().strip()
assert supervisor_command == 'python3 -u /mnt/d/dianzi/reports/runs/recovery_r04_minio_segment4_20261015/resume_minio.py'
assert child_command == '/tmp/dianzi-minio-r02-20261015/bin/minio server --quiet --address 127.0.0.1:29400 /tmp/dianzi-minio-r02-20261015/objects'
assert os.readlink('/proc/28049/cwd') == '/tmp/dianzi-minio-r02-20261015'
assert (GROUP / 'cgroup.procs').read_text().strip() == '28049'
ports = subprocess.run(['ss', '-ltnp', 'sport = :29400'], capture_output=True, text=True, check=True, timeout=5).stdout
assert '127.0.0.1:29400' in ports and 'pid=28049,' in ports
record = {'observed_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'), 'supervisor_pid': 28048, 'child_pid': 28049, 'supervisor_command': supervisor_command, 'child_command': child_command, 'cwd': os.readlink('/proc/28049/cwd'), 'port_pid_match': True, 'cgroup_pid_match': True, 'reason': 'Authorized bounded 6h observation requires MinIO successor with 6.5h maximum; original 2h segment ends early by its own stop request.', 'data_or_identity_reset': False}
(RUN / 'minio_transition_request.json').write_text(json.dumps(record, indent=2) + '\n')
(OLD / 'service_stop.request').write_text(json.dumps({'requested_at': record['observed_at'], 'reason': record['reason'], 'successor_run': str(RUN)}) + '\n')
deadline = time.monotonic() + 30
while not (OLD / 'service_end.json').exists() and time.monotonic() < deadline:
    time.sleep(0.5)
assert (OLD / 'service_end.json').exists(), 'owned predecessor did not close'
assert not (GROUP / 'cgroup.procs').read_text().strip(), 'owned MinIO child still active'
(RUN / 'minio_predecessor_end.json').write_text((OLD / 'service_end.json').read_text())
print(json.dumps({'status': 'owned_predecessor_closed', 'observed_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')}))
