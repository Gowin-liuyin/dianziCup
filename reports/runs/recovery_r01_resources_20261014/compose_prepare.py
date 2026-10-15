"""Install one verified Compose binary into the isolated Docker client directory."""

import argparse
import hashlib
import json
import os
import pathlib
import subprocess
from datetime import datetime, timedelta, timezone


CACHE = pathlib.Path('/tmp/dianzi-docker-static-r01-20261014/compose-v5.0.2')
CLIENT_CONFIG = pathlib.Path('/tmp/dianzi-docker-static-r01-20261014/runtime/client-config')
BASE_URL = 'https://github.com/docker/compose/releases/download/v5.0.2/'
ASSET = 'docker-compose-linux-x86_64'
ZONE = timezone(timedelta(hours=8))


def now():
    return datetime.now(ZONE).isoformat(timespec='seconds')


def run(command, timeout):
    started_at = now()
    result = subprocess.run(command, text=True, capture_output=True, timeout=timeout)
    print(json.dumps({'started_at': started_at, 'ended_at': now(), 'command': command,
                      'exit_code': result.returncode, 'stdout': result.stdout,
                      'stderr': result.stderr}), flush=True)
    if result.returncode:
        raise RuntimeError('Command failed with exit code ' + str(result.returncode))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['checksum', 'download', 'install'])
    args = parser.parse_args()
    CACHE.mkdir(mode=0o700, exist_ok=True)
    if args.action == 'checksum':
        run(['curl', '--fail', '--location', '--silent', '--show-error', '--max-time', '25',
             BASE_URL + ASSET + '.sha256', '--output', str(CACHE / (ASSET + '.sha256'))], 27)
        checksum = (CACHE / (ASSET + '.sha256')).read_text().strip()
        print(json.dumps({'official_checksum': checksum}))
    elif args.action == 'download':
        target = CACHE / ASSET
        command = ['curl', '--fail', '--location', '--silent', '--show-error', '--max-time', '50']
        if target.exists():
            command += ['--continue-at', '-']
        run([*command, BASE_URL + ASSET, '--output', str(target)], 52)
        print(json.dumps({'bytes': target.stat().st_size}))
    else:
        reference = (CACHE / (ASSET + '.sha256')).read_text().split()[0]
        assert len(reference) == 64
        target = CACHE / ASSET
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        assert actual == reference
        plugin_directory = CLIENT_CONFIG / 'cli-plugins'
        plugin_directory.mkdir(mode=0o700, exist_ok=True)
        plugin = plugin_directory / 'docker-compose'
        assert not plugin.exists()
        plugin.write_bytes(target.read_bytes())
        os.chmod(plugin, 0o700)
        docker = '/tmp/dianzi-docker-static-r01-20261014/portable/docker/docker'
        prefix = [docker, '--config', str(CLIENT_CONFIG), '--host',
                  'unix:///tmp/dianzi-docker-static-r01-20261014/runtime/docker.sock']
        result = run([*prefix, 'compose', 'version', '--short'], 10)
        assert result.stdout.strip() == '5.0.2'
        run([*prefix, 'compose', '--help'], 10)
        print(json.dumps({'installed_at': now(), 'binary_sha256': actual,
                          'publisher_checksum_matched': True, 'plugin_path': str(plugin)}))


if __name__ == '__main__':
    main()
