"""Stop the single root-authorized orphan through a verified Linux kernel pidfd."""

import json
import os
import select
import signal
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

OPS = Path('/mnt/d/dianzi-runtime-cache/r06-live-e310-operations-20261016')
CLOSE = OPS / 'close_20261016'
approval = json.loads((CLOSE / 'cleanup_authorization.json').read_text())
assert approval['root_cleanup_authorized'] is True
start = json.loads((OPS / 'minio_start.json').read_text())
expected = start['child']
assert expected['pid'] == 10928 and expected['start_ticks'] == '2144299'
assert expected['executable'] == '/tmp/dianzi-minio-r02-20261015/bin/minio'
group = Path('/sys/fs/cgroup/dianzi-r01-20261014/minio-r06-live-e310-20261016')
assert group.resolve() == group and start['cgroup'] == str(group)
boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert boot == start['boot_id'] == '8ee1634d-0b2e-4279-8426-2ae855e3b997'
assert group.joinpath('cgroup.procs').read_text().split() == [str(expected['pid'])]
assert not Path('/proc', str(start['supervisor']['pid'])).exists()
assert not (OPS / 'minio_end.json').exists()

def check_child_identity():
    proc = Path('/proc') / str(expected['pid'])
    actual = {
        'pid': expected['pid'],
        'start_ticks': proc.joinpath('stat').read_text().split()[21],
        'executable': str(proc.joinpath('exe').resolve()),
        'cgroup': proc.joinpath('cgroup').read_text().strip(),
    }
    assert actual == expected
    assert actual['cgroup'] == '0::/dianzi-r01-20261014/minio-r06-live-e310-20261016'
    return actual

before = check_child_identity()
pidfd = os.pidfd_open(expected['pid'], 0)
started = datetime.now(ZoneInfo('Asia/Shanghai'))
signals = []
try:
    check_child_identity()
    fdinfo = Path('/proc/self/fdinfo', str(pidfd)).read_text().splitlines()
    assert f'Pid:\t{expected["pid"]}' in fdinfo
    poller = select.poll()
    poller.register(pidfd, select.POLLIN)
    assert not poller.poll(0)
    signal.pidfd_send_signal(pidfd, signal.SIGTERM)
    signals.append('SIGTERM')
    exited = bool(poller.poll(10000))
    if not exited:
        signal.pidfd_send_signal(pidfd, signal.SIGKILL)
        signals.append('SIGKILL')
        exited = bool(poller.poll(5000))
    assert exited
    remaining = group.joinpath('cgroup.procs').read_text().split()
    assert not remaining
finally:
    os.close(pidfd)
receipt = {
    'started_at': started.isoformat(),
    'ended_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
    'boot_id': boot,
    'identity_before': before,
    'pidfd_kernel_exit_ack': exited,
    'signals_sent': signals,
    'maximum_term_wait_seconds': 10,
    'maximum_kill_wait_seconds': 5,
    'final_group_procs': remaining,
    'old_supervisor_missing': True,
    'original_helper_end_receipt_missing': True,
    'raw_or_volume_deleted': False,
    'collector_restarted': False,
}
with (CLOSE / 'minio_cleanup_receipt.json').open('x') as output:
    json.dump(receipt, output, indent=2)
    output.write('\n')
print(json.dumps(receipt))
