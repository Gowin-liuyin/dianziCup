#!/bin/sh
set -eu
cache=/tmp/dianzi-docker-static-r01-20261014
test "$(realpath -m "$cache")" = "$cache"
test -x "$cache/portable/docker/dockerd"
test ! -e "$cache/runtime"
test -d /sys/fs/cgroup/dianzi-r01-20261014
test -z "$(cat /sys/fs/cgroup/dianzi-r01-20261014/cgroup.procs)"
date -Iseconds
for binary in docker dockerd containerd runc; do
    "$cache/portable/docker/$binary" --version
done
nohup python3 /mnt/d/dianzi/reports/runs/recovery_r01_socket_root_cause_20261014/supervise_isolated_daemon.py \
    > "$cache/supervisor.log" 2>&1 < /dev/null &
printf 'launcher_pid=%s\n' "$!"
