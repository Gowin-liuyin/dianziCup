#!/bin/sh
set -eu
source_directory=/mnt/d/dianzi/reports/runs/recovery_r01_socket_root_cause_20261014
cache=/tmp/dianzi-docker-static-r01-20261014
python3 "$source_directory/delegate_project_controllers.py"
sh "$source_directory/start_isolated_daemon.sh"
attempt=0
while [ "$attempt" -lt 12 ]; do
    if [ -S "$cache/runtime/docker.sock" ]; then
        "$cache/portable/docker/docker" --config "$cache/runtime/client-config" \
            --host "unix://$cache/runtime/docker.sock" version --format '{{json .Server}}'
        exit "$?"
    fi
    attempt=$((attempt + 1))
    sleep 1
done
cat "$cache/supervisor.log"
exit 1
