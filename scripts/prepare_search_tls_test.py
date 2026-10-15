"""Create one bounded, loopback-only TLS test project; never manage another project."""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import socket
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGE = (
    "opensearchproject/opensearch@sha256:"
    "7b9517dff561f54456fad947f11820fa595a340fd1034fc63d57b77f724b3f8f"
)


def validate_identity(run_id: str, private_directory: Path) -> str:
    """Reject shared names and repository paths before writing PKI or touching Docker."""
    if not re.fullmatch(r"r01_tls_[a-z0-9_]{1,64}", run_id):
        raise ValueError(
            "TLS run ID must start with r01_tls_ and contain only lowercase letters/digits/_"
        )
    if not private_directory.is_absolute() or private_directory.resolve().is_relative_to(ROOT):
        raise ValueError("TLS private directory must be absolute and outside the repository")
    return "dianzi-test-" + run_id


def docker_command() -> list[str]:
    command = json.loads(os.environ.get("DIANZI_DOCKER_COMMAND_JSON", '["docker"]'))
    if (
        not isinstance(command, list)
        or not command
        or not all(isinstance(part, str) for part in command)
    ):
        raise ValueError("Docker command must be a nonempty JSON string array")
    return command


def run_command(
    arguments: list[str],
    *,
    environment: dict[str, str] | None = None,
    cwd: Path | None = None,
    timeout: int = 30,
) -> str:
    """Keep password hashes and command failure payloads out of logs."""
    result = subprocess.run(
        arguments,
        env=environment,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"TLS fixture command failed (exit {result.returncode})")
    return result.stdout


def prepare_pki(directory: Path, command: list[str], password: str) -> None:
    pki = directory / "pki"
    security = directory / "security"
    pki.mkdir(mode=0o700)
    security.mkdir(mode=0o700)

    def openssl(*arguments: str) -> None:
        run_command(["openssl", *arguments], cwd=pki, timeout=20)

    for name in ("root-ca", "node", "admin", "wrong-ca"):
        openssl(
            "genpkey",
            "-algorithm",
            "RSA",
            "-pkeyopt",
            "rsa_keygen_bits:2048",
            "-out",
            name + "-key.pem",
        )
    for name, subject in (
        ("root-ca", "/O=Dianzi/CN=R01 TLS Test CA"),
        ("wrong-ca", "/O=Dianzi/CN=Untrusted R01 Test CA"),
    ):
        openssl(
            "req",
            "-x509",
            "-new",
            "-key",
            name + "-key.pem",
            "-sha256",
            "-days",
            "3",
            "-subj",
            subject,
            "-addext",
            "basicConstraints=critical,CA:TRUE",
            "-addext",
            "keyUsage=critical,keyCertSign,cRLSign",
            "-out",
            name + ".pem",
        )
    for name, common_name, serial, extensions in (
        (
            "node",
            "opensearch",
            "1001",
            (
                "subjectAltName=DNS:opensearch,DNS:localhost\n"
                "extendedKeyUsage=serverAuth,clientAuth\n"
            ),
        ),
        ("admin", "security-admin", "1002", "extendedKeyUsage=clientAuth\n"),
    ):
        openssl(
            "req",
            "-new",
            "-key",
            name + "-key.pem",
            "-subj",
            "/O=Dianzi/OU=AIIntel/CN=" + common_name,
            "-out",
            name + ".csr",
        )
        (pki / (name + ".ext")).write_text(
            "basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\n"
            + extensions,
            encoding="utf-8",
        )
        openssl(
            "x509",
            "-req",
            "-in",
            name + ".csr",
            "-CA",
            "root-ca.pem",
            "-CAkey",
            "root-ca-key.pem",
            "-set_serial",
            serial,
            "-days",
            "3",
            "-sha256",
            "-extfile",
            name + ".ext",
            "-out",
            name + ".pem",
        )
    for name in ("root-ca.pem", "node.pem", "admin.pem", "wrong-ca.pem"):
        (pki / name).chmod(0o644)
    operator = [
        *command,
        "run",
        "--rm",
        "--pull",
        "never",
        "--network",
        "none",
        "--user",
        "0",
        "--memory",
        "256m",
        "--cpus",
        ".2",
        "--pids-limit",
        "128",
    ]
    run_command(
        [
            *operator,
            "--mount",
            f"type=bind,src={security},dst=/out",
            "--entrypoint",
            "/bin/sh",
            IMAGE,
            "-c",
            "cp /usr/share/opensearch/config/opensearch-security/*.yml /out/",
        ],
        timeout=30,
    )
    hashed = run_command(
        [
            *operator,
            "--env",
            "DIANZI_TLS_PASSWORD",
            "--entrypoint",
            "/usr/share/opensearch/plugins/opensearch-security/tools/hash.sh",
            IMAGE,
            "-env",
            "DIANZI_TLS_PASSWORD",
        ],
        environment=dict(os.environ, DIANZI_TLS_PASSWORD=password),
        timeout=30,
    )
    password_hash = next(line.strip() for line in hashed.splitlines() if line.startswith("$2"))
    (security / "internal_users.yml").write_text(
        '_meta:\n  type: internalusers\n  config_version: 2\nai_intel_search:\n  hash: "'
        + password_hash
        + '"\n  reserved: false\n  backend_roles: [ai_intel_health]\n',
        encoding="utf-8",
    )
    (security / "roles.yml").write_text(
        "_meta:\n  type: roles\n  config_version: 2\nai_intel_health:\n"
        '  cluster_permissions: ["cluster:monitor/health"]\n',
        encoding="utf-8",
    )
    (security / "roles_mapping.yml").write_text(
        "_meta:\n  type: rolesmapping\n  config_version: 2\nai_intel_health:\n"
        "  backend_roles: [ai_intel_health]\n",
        encoding="utf-8",
    )
    run_command(
        [
            *operator,
            "--mount",
            f"type=bind,src={directory},dst=/fixture",
            "--entrypoint",
            "/bin/sh",
            IMAGE,
            "-c",
            (
                "chown -R 1000:1000 /fixture/security; chmod 700 /fixture/security; "
                "chmod 600 /fixture/security/*.yml; chown 1000:1000 /fixture/pki/node-key.pem; "
                "chmod 600 /fixture/pki/node-key.pem"
            ),
        ],
        timeout=30,
    )


def compose_command(command: list[str], project: str, host_network: bool) -> list[str]:
    compose = [
        *command,
        "compose",
        "--project-name",
        project,
        "-f",
        str(ROOT / "infra/compose/compose.search-secure.test.yaml"),
    ]
    if host_network:
        compose += [
            "-f",
            str(ROOT / "infra/compose/compose.search-secure.test.host.yaml"),
        ]
    return compose


def require_owned_container(command: list[str], project: str, run_id: str) -> None:
    """All project containers must be this run's sole OpenSearch service before mutation."""
    containers = run_command(
        [
            *command,
            "ps",
            "-aq",
            "--no-trunc",
            "--filter",
            "label=com.docker.compose.project=" + project,
        ]
    ).split()
    if containers != [
        run_command([*command, "inspect", project + "-opensearch-1", "--format", "{{.Id}}"]).strip()
    ]:
        raise ValueError("TLS project does not contain exactly the expected container")
    labels = json.loads(
        run_command(
            [
                *command,
                "inspect",
                project + "-opensearch-1",
                "--format",
                "{{json .Config.Labels}}",
            ]
        )
    )
    if (
        labels.get("com.docker.compose.project") != project
        or labels.get("com.docker.compose.service") != "opensearch"
        or labels.get("io.dianzi.search-tls.run-id") != run_id
    ):
        raise ValueError("TLS container ownership labels do not match")


def wait_for_listener(port: int) -> None:
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return
        except OSError:
            time.sleep(1)
    raise RuntimeError("TLS fixture listener did not become available")


def create_fixture(arguments: argparse.Namespace) -> None:
    directory = arguments.private_directory
    project = validate_identity(arguments.run_id, directory)
    if not 1024 <= arguments.port <= 65535 or not 1024 <= arguments.transport_port <= 65535:
        raise ValueError("TLS fixture ports must be unprivileged valid ports")
    if arguments.port == arguments.transport_port:
        raise ValueError("TLS fixture ports must be distinct")
    command = docker_command()
    if run_command(
        [
            *command,
            "ps",
            "-aq",
            "--filter",
            "label=com.docker.compose.project=" + project,
        ]
    ).strip():
        raise ValueError("TLS project already exists")
    for port in (arguments.port, arguments.transport_port):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", port))
    run_command([*command, "image", "inspect", IMAGE])
    os.umask(0o077)
    directory.mkdir(mode=0o700, exist_ok=False)
    password = secrets.token_urlsafe(48) + "aA1!"
    values = {
        "TEST_SEARCH_TLS_URL": f"https://localhost:{arguments.port}",
        "TEST_SEARCH_TLS_USERNAME": "ai_intel_search",
        "TEST_SEARCH_TLS_PASSWORD": password,
        "TEST_SEARCH_TLS_CA_FILE": str(directory / "pki/root-ca.pem"),
        "TEST_SEARCH_TLS_WRONG_CA_FILE": str(directory / "pki/wrong-ca.pem"),
        "TEST_SEARCH_TLS_RUN_ID": arguments.run_id,
        "TEST_SEARCH_TLS_PROJECT": project,
        "TEST_SEARCH_TLS_CONTAINER": project + "-opensearch-1",
        "TEST_SEARCH_TLS_PORT": str(arguments.port),
        "TEST_SEARCH_TLS_TRANSPORT_PORT": str(arguments.transport_port),
        "TEST_SEARCH_TLS_NODE_CERT": str(directory / "pki/node.pem"),
        "TEST_SEARCH_TLS_NODE_KEY": str(directory / "pki/node-key.pem"),
    }
    (directory / "connection.json").write_text(
        json.dumps({"host_network": arguments.host_network, "environment": values}),
        encoding="utf-8",
    )
    prepare_pki(directory, command, password)
    environment = dict(os.environ, **values, COMPOSE_DISABLE_ENV_FILE="1")
    compose = compose_command(command, project, arguments.host_network)
    run_command([*compose, "up", "-d", "--pull", "never"], environment=environment, timeout=60)
    require_owned_container(command, project, arguments.run_id)
    wait_for_listener(arguments.port)
    network = "host" if arguments.host_network else project + "_private"
    host = "localhost" if arguments.host_network else "opensearch"
    port = str(arguments.port) if arguments.host_network else "9200"
    run_command(
        [
            *command,
            "run",
            "--rm",
            "--pull",
            "never",
            "--network",
            network,
            "--user",
            "0",
            "--memory",
            "512m",
            "--cpus",
            ".2",
            "--pids-limit",
            "128",
            "--mount",
            f"type=bind,src={directory / 'pki'},dst=/pki,readonly",
            "--mount",
            f"type=bind,src={directory / 'security'},dst=/security,readonly",
            "--entrypoint",
            "/usr/share/opensearch/plugins/opensearch-security/tools/securityadmin.sh",
            IMAGE,
            "-h",
            host,
            "-p",
            port,
            "-cn",
            "dianzi-ai-intel",
            "-cd",
            "/security",
            "-cacert",
            "/pki/root-ca.pem",
            "-cert",
            "/pki/admin.pem",
            "-key",
            "/pki/admin-key.pem",
            "-ff",
        ],
        timeout=180,
    )
    run_command(
        [*compose, "up", "-d", "--wait", "--wait-timeout", "180", "--pull", "never"],
        environment=environment,
        timeout=200,
    )
    if arguments.github_env:
        print("::add-mask::" + password)
        with arguments.github_env.open("a", encoding="utf-8") as output:
            for name, value in values.items():
                output.write(f"{name}={value}\n")
    print(
        json.dumps(
            {
                "fixture": "ready",
                "project": project,
                "url": values["TEST_SEARCH_TLS_URL"],
            }
        )
    )


def cleanup_fixture(arguments: argparse.Namespace) -> None:
    project = validate_identity(arguments.run_id, arguments.private_directory)
    connection = arguments.private_directory / "connection.json"
    if not connection.is_file():
        print(json.dumps({"fixture": "not_created", "project": project}))
        return
    configuration = json.loads(connection.read_text(encoding="utf-8"))
    values = configuration["environment"]
    if (
        values["TEST_SEARCH_TLS_PROJECT"] != project
        or values["TEST_SEARCH_TLS_RUN_ID"] != arguments.run_id
    ):
        raise ValueError("TLS private configuration belongs to a different run")
    command = docker_command()
    if run_command(
        [
            *command,
            "ps",
            "-aq",
            "--filter",
            "label=com.docker.compose.project=" + project,
        ]
    ).strip():
        require_owned_container(command, project, arguments.run_id)
        run_command(
            [*compose_command(command, project, configuration["host_network"]), "down"],
            environment=dict(os.environ, **values, COMPOSE_DISABLE_ENV_FILE="1"),
            timeout=60,
        )
    print(json.dumps({"fixture": "stopped", "project": project, "volumes": "preserved"}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "cleanup"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--private-directory", type=Path, required=True)
    parser.add_argument("--port", type=int, default=29204)
    parser.add_argument("--transport-port", type=int, default=29304)
    parser.add_argument("--host-network", action="store_true")
    parser.add_argument("--github-env", type=Path)
    arguments = parser.parse_args()
    try:
        if arguments.action == "create":
            create_fixture(arguments)
        else:
            cleanup_fixture(arguments)
    except (
        OSError,
        RuntimeError,
        ValueError,
        StopIteration,
        subprocess.TimeoutExpired,
    ) as error:
        parser.exit(1, f"blocked: isolated TLS fixture unavailable ({type(error).__name__})\n")


if __name__ == "__main__":
    main()
