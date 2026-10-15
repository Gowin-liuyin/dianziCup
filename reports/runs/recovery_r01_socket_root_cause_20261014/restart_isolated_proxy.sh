#!/bin/sh
set -eu
source_directory=/mnt/d/dianzi/reports/runs/recovery_r01_socket_root_cause_20261014
cache=/tmp/dianzi-docker-static-r01-20261014
python3 "$source_directory/stop_empty_isolated_daemon.py"
nohup python3 "$source_directory/supervise_isolated_daemon.py" \
    > "$cache/supervisor-proxy.log" 2>&1 < /dev/null &
printf 'replacement_supervisor_pid=%s\n' "$!"
