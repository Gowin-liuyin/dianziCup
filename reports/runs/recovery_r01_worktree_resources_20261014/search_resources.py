"""Prepare a root-only loopback OpenSearch test node with no host sysctl changes."""

import argparse
import ipaddress
import json
import os
import pathlib
import socket
import subprocess
import sys
import urllib.request


PRIOR_DIRECTORY = pathlib.Path(__file__).resolve().parent.parent / 'recovery_r01_resources_20261014'
sys.path.insert(0, str(PRIOR_DIRECTORY))
sys.dont_write_bytecode = True
import resources


CONTAINER = 'dianzi-test-r01_20261014-opensearch'
VOLUME = 'dianzi-test-r01_20261014-opensearch-data'
CONFIG_DIRECTORY = resources.RUNTIME / 'test-opensearch-r01_20261014'
IMAGE_TAG = 'opensearchproject/opensearch:2.17.0'
BASE_URL = 'http://127.0.0.1:29200'
PERFORMANCE_CONFIG_PATH = '/usr/share/opensearch/config/opensearch-performance-analyzer/performance-analyzer.properties'


def pull(image_tag: str = IMAGE_TAG, timeout_seconds: int = 180) -> None:
    command = [resources.DOCKER, '--config', str(resources.RUNTIME / 'client-config'),
               '--host', 'unix://' + str(resources.RUNTIME / 'docker.sock'), 'pull', image_tag]
    started_at = resources.now()
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout_seconds)
    except subprocess.TimeoutExpired as failure:
        print(json.dumps({'started_at': started_at, 'ended_at': resources.now(), 'command': command,
                          'exit_code': 124, 'timeout_seconds': timeout_seconds,
                          'partial_stdout': (failure.stdout or b'').decode(errors='replace'),
                          'partial_stderr': (failure.stderr or b'').decode(errors='replace')}), flush=True)
        raise
    print(json.dumps({'started_at': started_at, 'ended_at': resources.now(), 'command': command,
                      'exit_code': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}), flush=True)
    assert result.returncode == 0
    result = resources.docker(['image', 'inspect', image_tag, '--format', '{{json .RepoDigests}}'])
    print(json.dumps({'at': resources.now(), 'image_digests': json.loads(result.stdout)}))


def pull_ecr() -> None:
    ecr_tag = 'public.ecr.aws/opensearchproject/opensearch:2.17.0'
    pull(ecr_tag, 300)
    prepare_image()


def prepare_image() -> None:
    ecr_tag = 'public.ecr.aws/opensearchproject/opensearch:2.17.0'
    result = resources.docker(['image', 'inspect', ecr_tag])
    image_metadata = json.loads(result.stdout)[0]
    ecr_image = image_metadata['Id']
    assert ecr_image == 'sha256:7b9517dff561f54456fad947f11820fa595a340fd1034fc63d57b77f724b3f8f'
    assert image_metadata['Descriptor']['digest'] == ecr_image
    assert image_metadata['Architecture'] == 'amd64' and image_metadata['Os'] == 'linux'
    assert image_metadata['Config']['Labels']['org.label-schema.version'] == '2.17.0'
    current = resources.docker(['image', 'inspect', IMAGE_TAG, '--format', '{{.Id}}'], check=False)
    if current.returncode:
        resources.docker(['image', 'tag', ecr_tag, IMAGE_TAG])
    else:
        assert current.stdout.strip() == ecr_image


def image_configuration() -> None:
    result = resources.docker(['run', '--rm', '--network', 'none', '--read-only',
                              '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                              '--memory', '64m', '--memory-swap', '64m', '--cpus', '0.1',
                              '--pids-limit', '16', '--cgroup-parent', '/dianzi-r01-20261014',
                              '--entrypoint', 'bash', IMAGE_TAG, '-c',
                              'id -u opensearch; cat /usr/share/opensearch/opensearch-docker-entrypoint.sh; '
                              'cat ' + PERFORMANCE_CONFIG_PATH])
    assert result.stdout.splitlines()[0] == '1000'
    print(json.dumps({'at': resources.now(), 'host_vm_max_map_count':
                      pathlib.Path('/proc/sys/vm/max_map_count').read_text().strip()}))


def start() -> None:
    assert not CONFIG_DIRECTORY.exists()
    assert resources.inspect_named('container', CONTAINER) is None
    assert resources.inspect_named('volume', VOLUME) is None
    for port in (29200, 29300, 29600, 29650):
        with socket.socket() as probe:
            assert probe.connect_ex(('127.0.0.1', port)) != 0
    lifecycle = json.loads((resources.RUNTIME / 'lifecycle.json').read_text())
    assert lifecycle['ended_at'] is None and lifecycle['deadline'] == '2026-10-17T21:49:15+08:00'
    CONFIG_DIRECTORY.mkdir(mode=0o700)
    os.chmod(CONFIG_DIRECTORY, 0o700)
    result = resources.docker(['image', 'inspect', IMAGE_TAG, '--format', '{{json .RepoDigests}}'])
    image_digest = json.loads(result.stdout)[0]
    result = resources.docker(['run', '--rm', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
                              '--security-opt', 'no-new-privileges', '--memory', '64m',
                              '--memory-swap', '64m', '--cpus', '0.1', '--pids-limit', '16',
                              '--cgroup-parent', '/dianzi-r01-20261014', '--entrypoint', 'cat',
                              image_digest, PERFORMANCE_CONFIG_PATH])
    analyzer_lines = [line for line in result.stdout.splitlines()
                      if not line.lstrip().startswith(('webservice-bind-host', 'webservice-listener-port', 'rpc-port'))]
    analyzer_lines.extend(['webservice-bind-host = 127.0.0.1',
                           'webservice-listener-port = 29600', 'rpc-port = 29650'])
    analyzer_path = CONFIG_DIRECTORY / 'performance-analyzer.properties'
    analyzer_path.write_text('\n'.join(analyzer_lines) + '\n')
    os.chmod(analyzer_path, 0o600)
    os.chown(analyzer_path, 1000, 1000)
    private_config = {'DIANZI_TEST_RUN_ID': 'r01_20261014', 'TEST_OPENSEARCH_URL': BASE_URL,
                      'OPENSEARCH_URL': BASE_URL, 'NO_PROXY': '127.0.0.1,localhost',
                      'created_at': resources.now(), 'image_digest': image_digest,
                      'test_service': True, 'test_security_plugin_disabled': True}
    config_path = CONFIG_DIRECTORY / 'connection.json'
    config_path.write_text(json.dumps(private_config))
    os.chmod(config_path, 0o600)
    resources.docker(['volume', 'create', '--label', 'dianzi.project=dianzi-test-r01_20261014',
                      '--label', 'dianzi.mode=test', VOLUME])
    resources.docker(['run', '--detach', '--name', CONTAINER, '--network', 'host',
                      '--cgroup-parent', '/dianzi-r01-20261014', '--memory', '2g',
                      '--memory-swap', '2g', '--cpus', '0.75', '--pids-limit', '256',
                      '--security-opt', 'no-new-privileges', '--restart', 'no',
                      '--label', 'dianzi.project=dianzi-test-r01_20261014', '--label', 'dianzi.mode=test',
                      '--ulimit', 'nofile=65536:65536', '--log-driver', 'local',
                      '--log-opt', 'max-size=10m', '--log-opt', 'max-file=2',
                      '--env', 'discovery.type=single-node', '--env', 'network.host=127.0.0.1',
                      '--env', 'http.port=29200', '--env', 'transport.port=29300',
                      '--env', 'cluster.name=dianzi-r01-test', '--env', 'node.name=dianzi-r01-test-node',
                      '--env', 'node.store.allow_mmap=false', '--env', 'DISABLE_INSTALL_DEMO_CONFIG=true',
                      '--env', 'DISABLE_SECURITY_PLUGIN=true', '--env', 'OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m',
                      '--env', 'DISABLE_PERFORMANCE_ANALYZER_AGENT_CLI=true',
                      '--mount', 'type=volume,src=' + VOLUME + ',dst=/usr/share/opensearch/data',
                      '--mount', 'type=bind,src=' + str(analyzer_path) + ',dst=' + PERFORMANCE_CONFIG_PATH + ',readonly',
                      '--health-cmd', 'curl -fsS --noproxy 127.0.0.1 http://127.0.0.1:29200/_cluster/health',
                      '--health-interval', '10s', '--health-timeout', '3s', '--health-retries', '18',
                      image_digest])
    print(json.dumps({'at': resources.now(), 'private_config': str(config_path),
                      'vm_max_map_count_unchanged': pathlib.Path('/proc/sys/vm/max_map_count').read_text().strip(),
                      'node_store_allow_mmap': False, 'image_digest': image_digest}))


def request(method: str, path: str, body: dict | None = None) -> dict:
    payload = None if body is None else json.dumps(body).encode()
    request_object = urllib.request.Request(BASE_URL + path, data=payload, method=method,
                                           headers={'Content-Type': 'application/json'})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request_object, timeout=5) as response:
        result = json.loads(response.read())
        print(json.dumps({'at': resources.now(), 'http_method': method, 'path': path,
                          'status': response.status, 'response': result}))
        return result


def smoke() -> None:
    assert request('GET', '/')['version']['number'] == '2.17.0'
    assert request('GET', '/_cluster/health')['status'] in ('green', 'yellow')
    assert request('PUT', '/r01-resource-smoke', {'settings': {'number_of_shards': 1,
                                                            'number_of_replicas': 0}})['acknowledged']
    assert request('PUT', '/r01-resource-smoke/_doc/real-input?refresh=true',
                   {'title': 'AI vulnerability evidence', 'mode': 'test'})['result'] == 'created'
    result = request('POST', '/r01-resource-smoke/_search', {'query': {'match': {'title': 'vulnerability'}}})
    assert result['hits']['total']['value'] == 1
    node_result = request('GET', '/_nodes/settings?flat_settings=true')
    settings = next(iter(node_result['nodes'].values()))['settings']
    assert settings['node.store.allow_mmap'] == 'false'
    assert settings['network.host'] == '127.0.0.1'


def limits() -> None:
    result = resources.docker(['inspect', '--format', '{{json .State}}', CONTAINER])
    state = json.loads(result.stdout)
    assert state['Running'] and not state['OOMKilled']
    cgroup_line = pathlib.Path('/proc/' + str(state['Pid']) + '/cgroup').read_text().strip()
    assert cgroup_line.startswith('0::/dianzi-r01-20261014/')
    cgroup_path = pathlib.Path('/sys/fs/cgroup') / cgroup_line.split('::', 1)[1].lstrip('/')
    limits = {key: (cgroup_path / key).read_text().strip()
              for key in ('memory.max', 'memory.swap.max', 'cpu.max', 'pids.max')}
    assert limits == {'memory.max': '2147483648', 'memory.swap.max': '0',
                      'cpu.max': '75000 100000', 'pids.max': '256'}
    result = subprocess.run(['ss', '-ltnp', '( sport = :29200 or sport = :29300 or sport = :29600 or sport = :29650 )'],
                            capture_output=True, text=True, timeout=5, check=True)
    addresses = {listener_endpoint(line.split()[3]) for line in result.stdout.splitlines()[1:]}
    assert {('127.0.0.1', 29200), ('127.0.0.1', 29300)}.issubset(addresses)
    assert all(address[0] == '127.0.0.1' for address in addresses)
    all_listeners = subprocess.run(['ss', '-ltnp'], capture_output=True, text=True, timeout=5, check=True)
    node_listeners = [line for line in all_listeners.stdout.splitlines()[1:]
                      if 'pid=' + str(state['Pid']) + ',' in line]
    assert node_listeners and all(listener_endpoint(line.split()[3])[0] == '127.0.0.1'
                                  for line in node_listeners)
    print(json.dumps({'at': resources.now(), 'kernel_cgroup': str(cgroup_path), 'kernel_limits': limits,
                      'listen_command': result.args, 'exit_code': result.returncode,
                      'listen_output': result.stdout, 'private_config_mode':
                      oct((CONFIG_DIRECTORY / 'connection.json').stat().st_mode & 0o777),
                      'all_main_node_listener_lines': node_listeners}))


def listener_endpoint(value: str) -> tuple[str, int]:
    host, port = value.rsplit(':', 1)
    address = ipaddress.ip_address(host.strip('[]'))
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return str(address), int(port)


def main() -> None:
    assert listener_endpoint('[::ffff:127.0.0.1]:29200') == ('127.0.0.1', 29200)
    assert listener_endpoint('0.0.0.0:29200')[0] != '127.0.0.1'
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['pull', 'pull-ecr', 'prepare-image', 'image-configuration', 'start', 'smoke', 'limits'])
    arguments = parser.parse_args()
    print(json.dumps({'started_at': resources.now(), 'action': arguments.action}), flush=True)
    actions = {'pull': pull, 'pull-ecr': pull_ecr, 'prepare-image': prepare_image,
               'image-configuration': image_configuration, 'start': start,
               'smoke': smoke, 'limits': limits}
    actions[arguments.action]()
    print(json.dumps({'ended_at': resources.now(), 'action': arguments.action, 'result': 'passed'}))


if __name__ == '__main__':
    main()
