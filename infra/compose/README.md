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
and their required services. Search is optional; when selected, supply its URL.
The backend application URLs use `postgres:5432`, `redis:6379` and, when selected,
the configured search endpoint inside the private network. Browser URLs use the
published localhost ports. `ALLOWED_ORIGINS` must be exact JSON origins.

Set `PYTHON_IMAGE`, `UV_IMAGE`, `NODE_IMAGE` to verified digest references for
Python 3.12, uv and Node 24 before building application images. Dockerfiles
install the checked-in locks, copy only required source/config files and use
nonroot application users. The CI service job uses explicit config-only image
placeholders, and does not build or start application images.

```powershell
docker compose --project-name dianzi-dev-myname -f infra/compose/compose.yaml --profile core --profile search up -d --wait
docker compose --project-name dianzi-dev-myname -f infra/compose/compose.yaml --profile app --profile worker --profile scheduler --profile frontend up -d --build
docker compose --project-name dianzi-dev-myname -f infra/compose/compose.yaml --profile core --profile search --profile app --profile worker --profile scheduler --profile frontend down
```

`down` preserves all named volumes. API readiness verifies the real dependency
connections and installed migration revision. Starting the application does not
migrate a database or create accounts. Apply migrations and create users through
the explicit management CLI after checking the target identity. Scheduler health
checks beat process liveness; it is not evidence that a business task completed.

The bounded data-service allocation is PostgreSQL 512 MiB/0.4 CPU/128 PIDs,
Redis 128 MiB/0.1 CPU/64 PIDs and OpenSearch 2 GiB/0.5 CPU/256 PIDs (512 MiB heap,
no mmap). Application services add 1.125 GiB/0.85 CPU. Persistent storage size
depends on source bytes and retained versions; no sustained capacity result is
claimed. The private network has no outbound route; external business traffic
requires the separately authorized gateway configuration.

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
