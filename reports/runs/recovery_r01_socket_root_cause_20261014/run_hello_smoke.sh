#!/bin/sh
set -eu
cache=/tmp/dianzi-docker-static-r01-20261014
name=dianzi-r01-hello-20261014
image=hello-world@sha256:11a3eb1597e864c51b3f56733cb2e8a90bf0c284bfc05f9444d81c558bc848aa
date -Iseconds
"$cache/portable/docker/docker" --config "$cache/runtime/client-config" \
    --host "unix://$cache/runtime/docker.sock" run --name "$name" \
    --network none --memory 64m --cpus 0.1 --pids-limit 16 --read-only \
    --cap-drop ALL --security-opt no-new-privileges=true "$image"
"$cache/portable/docker/docker" --config "$cache/runtime/client-config" \
    --host "unix://$cache/runtime/docker.sock" inspect "$name" \
    --format '{{json .State}} {{json .HostConfig.Memory}} {{json .HostConfig.NanoCpus}} {{json .HostConfig.PidsLimit}} {{json .HostConfig.NetworkMode}} {{json .HostConfig.CgroupParent}}'
