#!/bin/sh
set -eu
date -Iseconds
curl --proto '=https' --proto-redir '=https' --tlsv1.2 --silent --show-error \
    --head --connect-timeout 5 --max-time 15 https://registry-1.docker.io/v2/
cache=/tmp/dianzi-docker-static-r01-20261014
for path in /usr/lib/docker/cli-plugins/docker-compose \
    /usr/libexec/docker/cli-plugins/docker-compose \
    /usr/local/lib/docker/cli-plugins/docker-compose \
    /mnt/wsl/docker-desktop/cli-tools/usr/lib/docker/cli-plugins/docker-compose; do
    if [ -x "$path" ]; then
        printf 'compose_plugin=%s\n' "$path"
    fi
done
