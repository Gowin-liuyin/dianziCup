#!/bin/sh
set -eu
date -Iseconds
for directory in /sys/fs/cgroup /sys/fs/cgroup/dianzi-r01-20261014; do
    printf 'directory=%s\n' "$directory"
    if [ ! -d "$directory" ]; then
        printf 'directory_state=absent\n'
        continue
    fi
    stat -c 'owner=%u:%g mode=%a' "$directory"
    for name in cgroup.controllers cgroup.subtree_control cgroup.procs cgroup.type memory.max cpu.max pids.max; do
        if [ -r "$directory/$name" ]; then
            printf '%s=' "$name"
            if [ "$name" = cgroup.procs ]; then
                wc -l < "$directory/$name"
            else
                cat "$directory/$name"
            fi
        else
            printf '%s=absent_or_unreadable\n' "$name"
        fi
    done
done
pgrep -x dockerd || true
pgrep -x containerd || true
