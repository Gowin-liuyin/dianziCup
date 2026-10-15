#!/bin/sh
set -eu
cache=/tmp/dianzi-docker-static-r01-20261014
source_directory=/mnt/d/dianzi/reports/runs/recovery_r01_runtime_recovery_20261015
test "$(realpath -m "$cache")" = "$cache"
test -x "$cache/portable/docker/dockerd"
test -e "$cache/runtime/recovery-prepared.json"
test ! -e "$cache/runtime/dockerd.pid"
test ! -e "$cache/runtime/docker.sock"
nohup python3 "$source_directory/supervise_recovered_daemon.py" \
    > "$cache/supervisor-recovery-20261015.log" 2>&1 < /dev/null &
printf 'launcher_pid=%s\n' "$!"
attempt=0
while [ "$attempt" -lt 15 ]; do
    if "$cache/portable/docker/docker" --config "$cache/runtime/client-config" \
        --host "unix://$cache/runtime/docker.sock" version --format '{{json .Server}}' 2>/dev/null; then
        exit 0
    fi
    attempt=$((attempt + 1))
    sleep 1
done
printf 'daemon_not_ready_check_private_supervisor_log\n'
exit 1
