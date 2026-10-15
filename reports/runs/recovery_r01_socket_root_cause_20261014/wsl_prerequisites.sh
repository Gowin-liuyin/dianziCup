#!/bin/sh
set -eu
date -Iseconds
uname -rm
git --version
xz --version | head -n 1
ps --version | head -n 1
findmnt -t cgroup,cgroup2 -o TARGET,FSTYPE,OPTIONS
cat /sys/fs/cgroup/cgroup.controllers
grep -E '^(overlay|nodev[[:space:]]+overlay)$' /proc/filesystems || true
if [ -r /sys/module/apparmor/parameters/enabled ]; then
    printf 'apparmor='; cat /sys/module/apparmor/parameters/enabled
fi
grep '^Seccomp' /proc/self/status
ss -ltn 'sport = :55432 or sport = :56379 or sport = :59200'
