#!/bin/sh
set -eu
cache=/tmp/dianzi-docker-static-r01-20261014
destination=/mnt/d/dianzi/reports/runs/recovery_r01_socket_root_cause_20261014
test "$(realpath -m "$cache")" = "$cache"
test "$(realpath -m "$destination")" = "$destination"
cp "$cache/archive-manifest.json" "$destination/portable_archive_manifest.json"
cp "$cache/download-headers.log" "$destination/portable_download_initial_headers.log"
cp "$cache/download-headers-52466146.log" "$destination/portable_download_resume_headers.log"
cp "$cache/delegation-before.json" "$destination/portable_delegation_before.json"
cp "$cache/delegation-after.json" "$destination/portable_delegation_after.json"
cp "$cache/first-daemon-lifecycle.json" "$destination/portable_first_daemon_lifecycle.json"
cp "$cache/first-dockerd.log" "$destination/portable_first_dockerd.log"
if [ -f "$cache/runtime/lifecycle.json" ]; then
    cp "$cache/runtime/lifecycle.json" "$destination/portable_daemon_lifecycle.json"
fi
if [ -f "$cache/runtime/dockerd.log" ]; then
    python3 "$destination/redact_proxy_log.py"
fi
date -Iseconds
printf 'evidence_exported=yes\n'
