#!/bin/sh
set -eu
cache=/tmp/dianzi-docker-static-r01-20261014
date -Iseconds
curl --fail --silent --show-error --max-time 5 \
    --unix-socket "$cache/runtime/docker.sock" http://localhost/_ping
printf '\n'
"$cache/portable/docker/docker" --config "$cache/runtime/client-config" \
    --host "unix://$cache/runtime/docker.sock" info \
    --format '{{json .ServerVersion}} {{json .DockerRootDir}} {{json .CgroupDriver}} {{json .SecurityOptions}}'
cat "$cache/runtime/lifecycle.json"
for name in memory.max memory.swap.max cpu.max pids.max cgroup.procs; do
    printf '%s=' "$name"
    cat "/sys/fs/cgroup/dianzi-r01-20261014/$name"
done
