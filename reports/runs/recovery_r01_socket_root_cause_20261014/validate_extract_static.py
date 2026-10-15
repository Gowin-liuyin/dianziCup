"""Validate an official static archive before extracting into its dedicated cache."""

import hashlib
import json
import tarfile
from datetime import datetime
from pathlib import Path, PurePosixPath


cache = Path("/tmp/dianzi-docker-static-r01-20261014")
assert cache.resolve() == cache and not cache.is_symlink()
archive_path = cache / "docker-29.2.0.tgz.part"
extract_path = cache / "portable"
assert not extract_path.exists(), "Never overwrite an existing extraction."
assert 1_000_000 < archive_path.stat().st_size < 100_000_000
digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
members = []
with tarfile.open(archive_path, "r:gz") as archive:
    for member in archive.getmembers():
        relative_path = PurePosixPath(member.name)
        assert not relative_path.is_absolute() and ".." not in relative_path.parts
        assert relative_path.parts[0] == "docker"
        assert member.isdir() or member.isfile(), "Reject all links/devices/FIFOs."
        assert (extract_path / member.name).resolve().is_relative_to(extract_path)
        members.append({"name": member.name, "size": member.size,
                        "type": "directory" if member.isdir() else "file"})
    assert sum(member["size"] for member in members) < 500_000_000
    names = {member["name"] for member in members}
    assert {"docker/docker", "docker/dockerd", "docker/containerd", "docker/runc"} <= names
    extract_path.mkdir()
    archive.extractall(extract_path)
result = {"recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
          "official_url": "https://download.docker.com/linux/static/stable/x86_64/docker-29.2.0.tgz",
          "archive_path": str(archive_path), "archive_bytes": archive_path.stat().st_size,
          "local_sha256": digest, "publisher_checksum_verified": False,
          "checksum_limit": "Local SHA256 records the fetched bytes; no published reference hash was available.",
          "extract_path": str(extract_path), "members": members}
(cache / "archive-manifest.json").write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
