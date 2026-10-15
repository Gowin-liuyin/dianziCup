#!/bin/sh
set -u
date -Iseconds
id
for binary in docker dockerd containerd ctr runc iptables ip6tables ip nft slirp4netns rootlesskit unshare curl tar sha256sum; do
    location=$(command -v "$binary" 2>/dev/null || true)
    if [ -n "$location" ]; then
        printf '%s=%s\n' "$binary" "$location"
        readlink -f "$location"
    else
        printf '%s=missing\n' "$binary"
    fi
done
for name in dockerd containerd; do
    pgrep -x "$name" || true
done
if [ -S /var/run/docker.sock ]; then
    stat -c 'existing_socket=%n mode=%a uid=%u gid=%g' /var/run/docker.sock
else
    printf 'existing_socket=absent\n'
fi
df -h / /tmp /mnt/d
if command -v iptables >/dev/null 2>&1; then
    iptables --version
fi
if command -v unshare >/dev/null 2>&1; then
    unshare -m /bin/true
    printf 'mount_namespace_exit=%s\n' "$?"
fi
