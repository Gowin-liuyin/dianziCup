# R01 local and isolated deployment

Compose 2.24.4 or later is required for `include`, `!override` and `!reset`.
Supply configuration through the environment or a private `--env-file` outside
the repository. Set `COMPOSE_DISABLE_ENV_FILE=1` to prevent implicit `.env` loading.
`config/dev.env.example` lists names only: credentials, URLs, image references
and exclusive host ports must be supplied explicitly. Do not run `compose config`
into a shared log: its output includes interpolated credentials.

Choose an explicit `dianzi-dev-<name>` project. `core` starts PostgreSQL and
authenticated Redis; `search` adds OpenSearch with its security plugin enabled.
`app`, `worker`, `scheduler` and `frontend` select the actual runtime entrypoints
and their required services. The base application search endpoint is
`https://opensearch:9200`; select `search` and prepare its TLS resources before
expecting application readiness.
`COMPOSE_DATABASE_URL`, `COMPOSE_REDIS_URL` and `COMPOSE_ALLOWED_ORIGINS` are
deployment inputs: Compose maps them to the application variable names inside
containers. They do not configure a pytest or management process on the host.
The backend application URLs use `postgres:5432`, `redis:6379` and, when selected,
the configured search endpoint inside the private network. Browser URLs use the
published localhost ports. `ALLOWED_ORIGINS` must be exact JSON origins.

The Dockerfiles and Compose build arguments pin the actually pulled official
Python 3.12, uv 0.10.9 and Node 24 RepoDigests. Dockerfiles
install the checked-in locks, copy only required source/config files and use
nonroot application users. The CI service job does not build or start application images.

```powershell
docker compose --project-name dianzi-dev-myname -f infra/compose/compose.yaml --profile core up -d --wait
docker compose --project-name dianzi-dev-myname -f infra/compose/compose.yaml --profile app --profile worker --profile scheduler --profile frontend up -d --build
docker compose --project-name dianzi-dev-myname -f infra/compose/compose.yaml --profile core --profile search --profile app --profile worker --profile scheduler --profile frontend down
```

Profile `investigation` starts `python -m ai_intel.workers.investigation` on queue `ai_intel_investigations`. The default worker does not consume that queue. Declaring the profile is not evidence that an investigation trace has run.

`down` preserves all named volumes. API readiness verifies the real dependency
connections and installed migration revision. Starting the application does not
migrate a database or create accounts. From `backend/`, with `DATABASE_URL`
already in the environment, `uv run python ../scripts/migrate.py` applies
migrations to head and `uv run python ../scripts/admin_user.py` creates a user.
Neither script reads a `.env` file or prints the database URL. Confirm the
target database identity before either command. Scheduler health
checks beat process liveness; it is not evidence that a business task completed.

The bounded data-service allocation is PostgreSQL 512 MiB/0.4 CPU/128 PIDs,
Redis 128 MiB/0.1 CPU/64 PIDs and OpenSearch 2 GiB/0.5 CPU/256 PIDs (512 MiB heap,
no mmap). Application services add 1.125 GiB/0.85 CPU. Persistent storage size
depends on source bytes and retained versions; no sustained capacity result is
claimed. The private network has no outbound route; external business traffic
requires the separately authorized gateway configuration.

## Secure search initialization

The base disables the demo installer and enables HTTPS and transport TLS.
`OPENSEARCH_CA_HOST_FILE`, `OPENSEARCH_NODE_CERT_HOST_FILE`,
`OPENSEARCH_NODE_KEY_HOST_FILE` and `OPENSEARCH_SECURITY_CONFIG_HOST_DIRECTORY`
must point to prepared resources outside the repository and Docker build context.
Missing paths fall back to `/dev/null` so explicit HTTP test overlays can still
render; this is not a usable CA or security configuration and cannot produce a
healthy secure deployment. Bind mounts are read-only and do not create missing
host paths. Application containers receive only the public CA at
`/run/ai-intel/search/root-ca.pem`; node and administrator keys never enter them.

Issue a PKCS#8 node key and a CA-signed certificate with DNS SANs `opensearch`
and `localhost`. Its DN must match `CN=opensearch,OU=AIIntel,O=Dianzi` in the
checked-in configuration. A separate client administrator certificate must
match `CN=security-admin,OU=AIIntel,O=Dianzi`. Protect the containing directory
with mode 0700 and private keys with mode 0600. The actual pinned image runs as
UID/GID 1000; make its mounted node key and security configuration readable by
that user without exposing administrator or CA signing keys to the server.

Set `COMPOSE_OPENSEARCH_USERNAME` and inject the matching application password
through `COMPOSE_OPENSEARCH_PASSWORD`. The existing
`OPENSEARCH_INITIAL_ADMIN_PASSWORD` variable supplies the server health account
password; the demo installer remains disabled, so this variable does not create
an administrator. There is no default username or password. The account must
already be in `internal_users.yml` as a BCrypt hash and mapped to a role with
`cluster:monitor/health`; index read/write permissions require separate explicit
roles. Never embed userinfo in `OPENSEARCH_URL` or store plaintext passwords in
the security directory.

Start search without `--wait`, initialize the security index with the bundled
`securityadmin.sh`, then wait for its authenticated CA-verified health check.
The first start cannot become healthy before security initialization. Run the
administrator tool as a bounded temporary operator container with read-only
PKI/config mounts; the long-running server remains nonroot. For a normal bridge
project, replace the paths below with your private external directory and use
the project's private network:

```sh
docker compose --project-name dianzi-dev-myname -f infra/compose/compose.yaml --profile search up -d --pull never
docker run --rm --network dianzi-dev-myname_private --user 0 --memory 512m --cpus .2 --pids-limit 128 \
  --mount type=bind,src=/private/search/pki,dst=/pki,readonly \
  --mount type=bind,src=/private/search/security,dst=/security,readonly \
  --entrypoint /usr/share/opensearch/plugins/opensearch-security/tools/securityadmin.sh \
  opensearchproject/opensearch@sha256:7b9517dff561f54456fad947f11820fa595a340fd1034fc63d57b77f724b3f8f \
  -h opensearch -p 9200 -cn dianzi-ai-intel -cd /security \
  -cacert /pki/root-ca.pem -cert /pki/admin.pem -key /pki/admin-key.pem -ff
docker compose --project-name dianzi-dev-myname -f infra/compose/compose.yaml --profile search up -d --wait --wait-timeout 180 --pull never
```

Wait for the TLS listener before the bounded administrator command. It validates
the CA and hostname; do not add `-nhnv`, `curl -k` or disable application TLS
verification. The reproducible isolated test preparation is
`reports/runs/recovery_r01_search_tls_20261015/prepare_pki.py`: it uses OpenSSL,
the pinned image's `hash.sh -env`, random credentials, and an external root-only
directory. It deliberately refuses an existing directory. Its lab-specific
paths, three-day certificate lifetime and health-only role must be adapted
explicitly when preparing another isolated CI fixture.

For the authorized daemon without a bridge, `compose.search.secure.host.yaml`
selects only search with `--profile search`. Supply exclusive
`SECURE_OPENSEARCH_PORT` and `SECURE_OPENSEARCH_TRANSPORT_PORT`; both listeners
bind internally to 127.0.0.1 and published ports are cleared. The R01 TLS run
uses `dianzi-test-r01_tls_20261015`, 29202/29302 and a separate named data volume.
The actual operator command uses `--network host -h localhost -p 29202`.

See the official [2.17 Docker configuration](https://docs.opensearch.org/docs/2.17/install-and-configure/install-opensearch/docker/),
[TLS certificate settings](https://docs.opensearch.org/latest/security/configuration/tls/)
and [security index administration](https://docs.opensearch.org/latest/security/configuration/security-admin/).
The commands above were checked against the pinned 2.17 image's actual tools.

## Dedicated CI TLS fixture

`scripts/prepare_search_tls_test.py` replays the OpenSSL and pinned-image
`hash.sh -env`/`securityadmin.sh` preparation in a new external private directory.
It creates only one bounded secure search service, waits for its authenticated
CA-verified health check, and supplies the five `TEST_SEARCH_TLS_*` connection
inputs plus run/project/container identity. The test URL is `https://localhost`
on the selected port. Private keys and plaintext credentials stay outside the
repository; the account can only read cluster health. An existing directory or
project is refused. Pull the pinned image explicitly before calling `create`.

```sh
python scripts/prepare_search_tls_test.py create \
  --run-id r01_tls_ci_example --private-directory /private/dianzi-tls-ci-example \
  --port 29204 --transport-port 29304 --github-env "$GITHUB_ENV"
python scripts/dev.py check --scope integration --timeout-seconds 600
python scripts/prepare_search_tls_test.py cleanup \
  --run-id r01_tls_ci_example --private-directory /private/dianzi-tls-ci-example
```

`--github-env` appends the verified fixture inputs to the GitHub environment and
registers the random password as a log mask. Outside GitHub, load the environment
object from the private `connection.json` without printing it. Linux users do
not need host root permissions: bounded operator containers apply UID 1000
ownership to node keys and security configuration. The authorized daemon with
bridge networking disabled additionally uses `--host-network`; both HTTP and
transport bind to loopback. CI uses the ordinary private bridge by default.

`cleanup` checks the run ID, exact project/container and Compose ownership labels
before `down`, and preserves named volumes and external PKI. Missing resources
remain hard blocked errors in TLS tests. The complete integration scope includes
the seven real TLS/fault tests; it does not exclude their registered marker.

## Test projects

`compose.test.yaml` includes the base and replaces the development database and
ports. The database is `test_dianzi_<DIANZI_TEST_RUN_ID>`; supply a dedicated
`TEST_POSTGRES_USER`, random URL-safe test credentials and exclusive test ports.
The application URLs in this overlay use the container service names. The
`TEST_DATABASE_URL`, `TEST_REDIS_URL`, `TEST_OPENSEARCH_URL` consumed by host-side
tests use loopback and the published exclusive ports.

Set `DIANZI_TEST_COMPOSE_PROJECT=dianzi-test-<DIANZI_TEST_RUN_ID>` and
`DIANZI_TEST_COMPOSE_FILE` to the existing test entry file. The shared quality
entrypoint rejects a nonisolated PostgreSQL DSN before running tests or Compose.
Missing resources fail with `blocked`; no test resource is substituted or skipped.

`compose.test.host.yaml` is only for the specifically authorized Linux daemon
with bridge networking disabled. It clears published ports and bridge networks;
PostgreSQL, Redis, OpenSearch HTTP/transport, API and frontend bind internally to
127.0.0.1 on exclusive configured ports. It also changes application URLs to the
host-side loopback test URLs. It must not be used as a production deployment.
OpenSearch security is disabled only in explicit localhost test overlays.

The R01-infra run uses project `dianzi-test-r01_infra_20261015`, PostgreSQL 25436,
Redis 26383, OpenSearch 29201/29301. The private random connection configuration
is root-only outside this repository. The authorized daemon expires at
2026-10-17T21:49:15+08:00; this package does not extend it or change host limits.
