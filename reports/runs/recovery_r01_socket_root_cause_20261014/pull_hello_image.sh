#!/bin/sh
set -eu
cache=/tmp/dianzi-docker-static-r01-20261014
date -Iseconds
timeout 20s "$cache/portable/docker/docker" --config "$cache/runtime/client-config" \
    --host "unix://$cache/runtime/docker.sock" pull hello-world:latest
"$cache/portable/docker/docker" --config "$cache/runtime/client-config" \
    --host "unix://$cache/runtime/docker.sock" image inspect hello-world:latest \
    --format '{{json .RepoDigests}}'
