#!/bin/sh
set -eu
cache=/tmp/dianzi-docker-static-r01-20261014
test "$(realpath -m "$cache")" = "$cache"
test ! -L "$cache"
mkdir -p "$cache"
archive="$cache/docker-29.2.0.tgz.part"
download_size=0
if [ -f "$archive" ]; then
    download_size=$(stat -c %s "$archive")
fi
date -Iseconds
set +e
curl --proto '=https' --proto-redir '=https' --tlsv1.2 --fail --location \
    --connect-timeout 5 --max-time 20 --retry 0 --continue-at - \
    --dump-header "$cache/download-headers-$download_size.log" \
    --output "$archive" \
    https://download.docker.com/linux/static/stable/x86_64/docker-29.2.0.tgz
result=$?
set -e
printf 'curl_exit=%s\n' "$result"
if [ -f "$archive" ]; then
    stat -c 'downloaded_bytes=%s' "$archive"
fi
date -Iseconds
exit "$result"
