# home-internal-api

`home-internal-api` is a LAN-only JSON API for exposing `home-server` internal state to Home Assistant.

It is intentionally separate from `home-public-api`.

- `home-public-api`: externally safe APIs, billing, household-facing features
- `home-internal-api`: LAN-only monitoring APIs for `systemd`, Docker, host status, storage, and backups

## Goals

This API exists to provide Home Assistant with stable monitoring data for:

- `systemd` service state
- Docker container state
- basic host information
- storage and backup state
- future UPS, SMART, and log monitoring

Home Assistant is expected to read this with `rest` sensors and `template` binary sensors.

Because of that, the API is designed around:

- shallow JSON
- stable state strings
- summary counts already aggregated
- fixed keys for entity creation
- both per-domain endpoints and a summary endpoint

## v1 Scope

The recommended v1 surface is:

- `GET /api/status/health`
- `GET /api/status/summary`
- `GET /api/status/host`
- `GET /api/status/services`
- `GET /api/status/containers`

Current production targets on `home-server`:

- services: `glances`, `home-platform`, `home-internal-api`, `docker`
- containers: `home-platform-immich-server`, `home-platform-immich-redis`, `home-platform-immich-postgres`

## Design Principles

- LAN-only access
- protected by `x-internal-api-secret`
- light enough for Home Assistant polling every 30 to 60 seconds
- always returns JSON, including failure cases
- fixed keys that are easy to map to Home Assistant entities
- stable state vocabulary
- both summary and detailed endpoints

## Base Configuration

- Base URL example: `http://192.168.11.12:3010`
- Header auth: `x-internal-api-secret: <secret>`
- Content-Type: `application/json`
- Every response must include `ok`

## Stable State Values

### Service states

- `active`
- `inactive`
- `failed`
- `missing`
- `unknown`

### Container states

- `running`
- `stopped`
- `missing`
- `unknown`

## Endpoints

### `GET /api/status/health`

Minimal health check.

Example:

```json
{
  "ok": true
}
```

### `GET /api/status/summary`

Primary Home Assistant monitoring endpoint.

Returns:

- monitored service map
- monitored container map
- pre-aggregated summary counts
- host name
- update timestamp

Example:

```json
{
  "ok": true,
  "host": {
    "name": "home-server",
    "updatedAt": "2026-03-30T02:10:00+09:00"
  },
  "services": {
    "glances": "active",
    "home-platform": "active",
    "home-internal-api": "active",
    "docker": "active"
  },
  "containers": {
    "home-platform-immich-server": "running",
    "home-platform-immich-redis": "running",
    "home-platform-immich-postgres": "running"
  },
  "summary": {
    "servicesOk": 4,
    "servicesTotal": 4,
    "containersRunning": 3,
    "containersTotal": 3
  }
}
```

### `GET /api/status/services`

Service-focused endpoint.

Example:

```json
{
  "ok": true,
  "updatedAt": "2026-03-30T02:10:00+09:00",
  "items": [
    { "name": "glances", "state": "active" },
    { "name": "home-platform", "state": "active" },
    { "name": "home-internal-api", "state": "active" },
    { "name": "docker", "state": "active" }
  ]
}
```

### `GET /api/status/containers`

Container-focused endpoint.

Example:

```json
{
  "ok": true,
  "updatedAt": "2026-03-30T02:10:00+09:00",
  "items": [
    { "name": "home-platform-immich-server", "state": "running" },
    { "name": "home-platform-immich-redis", "state": "running" },
    { "name": "home-platform-immich-postgres", "state": "running" }
  ]
}
```

### `GET /api/status/host`

Basic host status for REST sensors.

Returns:

- uptime
- load average
- memory
- disk
- temperature
- optional network details

Example:

```json
{
  "ok": true,
  "updatedAt": "2026-03-30T02:10:00+09:00",
  "host": {
    "uptimeSeconds": 2483200,
    "load1": 1.12,
    "load5": 0.94,
    "load15": 0.88,
    "memoryUsedPercent": 51.2,
    "memoryFreeBytes": 4020602880,
    "rootDiskUsedPercent": 80.3,
    "dataDiskUsedPercent": 0.9,
    "dataDiskFreeBytes": 1849958400000,
    "cpuTemperatureC": 34.0
  }
}
```

## Home Assistant Data Rules

These rules are part of the API contract.

- keep nesting shallow enough for expressions like `value_json.summary.servicesOk`
- keep keys fixed so templates do not break
- keep state strings fixed and normalized
- always provide summary counts
- provide both map-style and array-style representations where useful

Why both matter:

- map responses are easier for Home Assistant entity templates like `value_json.services.glances`
- array responses are easier for human debugging

## Error Handling and Degradation

- secret mismatch returns `401`
- command execution timeout target: `3` to `5` seconds
- overall response target: under `1` second
- if one internal check fails, the endpoint still returns JSON
- failed checks should degrade to `unknown`
- `ok` should indicate whether the API successfully served a structured response, not whether every monitored dependency is healthy

## Non-Functional Requirements

- bind only on LAN
- run as a long-lived `systemd` service
- lightweight enough for frequent polling
- avoid heavy shelling or repeated expensive probes
- prefer caching or batched collection when helpful

## Future Endpoints

Likely follow-up endpoints:

- `GET /api/backup/status`
- `GET /api/storage/status`
- `GET /api/immich/status`
- `GET /api/smart/status`
- `GET /api/tasks/queue`

Suggested future data:

- backup last run time, success/failure, size, latest error
- `/srv/home-data` usage, free space, growth trend, mount state
- Immich container and volume state
- SMART health, temperature, reallocated sectors
- internal task queue depth

## Production Deployment

Current production deployment is:

- host: `home-server`
- app working copy: `/home/home-server/home-platform/apps/home-internal-api`
- parent project: `/home/home-server/home-platform`
- process manager: host `systemd`
- listen address: `0.0.0.0:3010`
- auth header: `x-internal-api-secret`

This service is intentionally not run as a Docker container in production.
It monitors the host itself, so host `systemd` is the simplest and most reliable setup.

## Production Environment

The production instance reads configuration from the parent project `.env`:

- file: `/home/home-server/home-platform/.env`

Required values:

```env
HOME_INTERNAL_API_HOSTNAME=home-server
HOME_INTERNAL_API_BIND_HOST=0.0.0.0
HOME_INTERNAL_API_PORT=3010
HOME_INTERNAL_API_SECRET=<secret>
HOME_INTERNAL_API_MONITORED_SERVICES=glances,home-platform,home-internal-api,docker
HOME_INTERNAL_API_MONITORED_CONTAINERS=home-platform-immich-server,home-platform-immich-redis,home-platform-immich-postgres
HOME_INTERNAL_API_DATA_DISK_PATH=/srv/home-data
```

Notes:

- `HOME_INTERNAL_API_BIND_HOST=0.0.0.0` is required so Home Assistant can reach the API over LAN
- `HOME_INTERNAL_API_HOSTNAME=home-server` controls `host.name` in the JSON response
- monitored container names should match the real Docker container names, not image names

## Production systemd Unit

Production unit path:

- `/etc/systemd/system/home-internal-api.service`

Recommended unit:

```ini
[Unit]
Description=home-internal-api
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/home-server/home-platform/apps/home-internal-api
EnvironmentFile=/home/home-server/home-platform/.env
ExecStart=/home/home-server/home-platform/apps/home-internal-api/.venv/bin/home-internal-api
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

## Production Setup Steps

Use this when rebuilding from scratch on `home-server`.

1. Place the repository under `/home/home-server/home-platform/apps/home-internal-api`.
2. Ensure `/home/home-server/home-platform/.env` contains the `HOME_INTERNAL_API_*` values above.
3. Create the virtual environment and install the package.
4. Install the `systemd` unit.
5. Enable and start the service.

Commands:

```bash
cd /home/home-server/home-platform/apps/home-internal-api
python3 -m venv .venv
.venv/bin/pip install -e .

sudo install -Dm644 deploy/systemd/home-internal-api.service /etc/systemd/system/home-internal-api.service
sudo systemctl daemon-reload
sudo systemctl enable --now home-internal-api.service
```

If the checked-in unit uses a different base path, edit `/etc/systemd/system/home-internal-api.service` to match the real host path before enabling it.

## Verification

Check the service:

```bash
sudo systemctl status home-internal-api.service --no-pager
sudo journalctl -u home-internal-api.service -f
sudo lsof -nP -iTCP:3010 -sTCP:LISTEN
```

Expected listener:

- `*:3010` or `0.0.0.0:3010`

Check the API locally:

```bash
curl -s -H 'x-internal-api-secret: <secret>' http://127.0.0.1:3010/api/status/health
curl -s -H 'x-internal-api-secret: <secret>' http://127.0.0.1:3010/api/status/summary | jq
```

Check the API over LAN:

```bash
curl -s -H 'x-internal-api-secret: <secret>' http://192.168.11.12:3010/api/status/summary | jq
```

Expected summary shape in production:

```json
{
  "ok": true,
  "host": {
    "name": "home-server"
  },
  "services": {
    "glances": "active",
    "home-platform": "active",
    "home-internal-api": "active",
    "docker": "active"
  },
  "containers": {
    "home-platform-immich-server": "running",
    "home-platform-immich-redis": "running",
    "home-platform-immich-postgres": "running"
  },
  "summary": {
    "servicesOk": 4,
    "servicesTotal": 4,
    "containersRunning": 3,
    "containersTotal": 3
  }
}
```

## Home Assistant Example

```yaml
rest:
  - resource: "http://192.168.11.12:3010/api/status/summary"
    scan_interval: 60
    timeout: 30
    headers:
      x-internal-api-secret: !secret home_internal_api_secret
    sensor:
      - name: "Internal Services OK"
        value_template: "{{ value_json.summary.servicesOk }}"
      - name: "Internal Services Total"
        value_template: "{{ value_json.summary.servicesTotal }}"
      - name: "Internal Containers Running"
        value_template: "{{ value_json.summary.containersRunning }}"
      - name: "Internal Containers Total"
        value_template: "{{ value_json.summary.containersTotal }}"
      - name: "Glances State"
        value_template: "{{ value_json.services.glances }}"
      - name: "Home Platform State"
        value_template: "{{ value_json.services['home-platform'] }}"
      - name: "Home Internal API State"
        value_template: "{{ value_json.services['home-internal-api'] }}"
      - name: "Docker State"
        value_template: "{{ value_json.services.docker }}"
      - name: "Immich Server State"
        value_template: "{{ value_json.containers['home-platform-immich-server'] }}"
      - name: "Immich Redis State"
        value_template: "{{ value_json.containers['home-platform-immich-redis'] }}"
      - name: "Immich Postgres State"
        value_template: "{{ value_json.containers['home-platform-immich-postgres'] }}"

template:
  - binary_sensor:
      - name: "Glances Healthy"
        state: "{{ is_state('sensor.glances_state', 'active') }}"
      - name: "Home Platform Healthy"
        state: "{{ is_state('sensor.home_platform_state', 'active') }}"
      - name: "Home Internal API Healthy"
        state: "{{ is_state('sensor.home_internal_api_state', 'active') }}"
      - name: "Docker Healthy"
        state: "{{ is_state('sensor.docker_state', 'active') }}"
      - name: "Immich Server Healthy"
        state: "{{ is_state('sensor.immich_server_state', 'running') }}"
      - name: "Immich Redis Healthy"
        state: "{{ is_state('sensor.immich_redis_state', 'running') }}"
      - name: "Immich Postgres Healthy"
        state: "{{ is_state('sensor.immich_postgres_state', 'running') }}"
```

## Implementation Notes

To keep the contract simple and reliable:

- configuration should declare the monitored services and containers explicitly
- the summary endpoint should be built from the same collectors as the detailed endpoints
- timestamps should use ISO 8601 with timezone offsets
- host and monitoring collectors should fail independently
- the state vocabulary above should be enforced in one normalization layer

## OpenAPI

The initial API contract is also described in [`openapi.yaml`](/Users/jagashira/work/github.com/Jagashira/home-internal-api/openapi.yaml).

## Python Implementation

This repository now includes a minimal Python API server implementation under [`src/home_internal_api`](/Users/jagashira/work/github.com/Jagashira/home-internal-api/src/home_internal_api).

Characteristics:

- Python standard library based
- runs on Linux `home-server`
- checks `systemctl` service state
- checks Docker container state
- returns JSON suitable for Home Assistant polling
- intended to run behind host `systemd`

## Configuration

Example environment file: [`.env.example`](/Users/jagashira/work/github.com/Jagashira/home-internal-api/.env.example)

Environment variables:

- `HOME_INTERNAL_API_BIND_HOST`
- `HOME_INTERNAL_API_PORT`
- `HOME_INTERNAL_API_SECRET`
- `HOME_INTERNAL_API_MONITORED_SERVICES`
- `HOME_INTERNAL_API_MONITORED_CONTAINERS`
- `HOME_INTERNAL_API_DATA_DISK_PATH`

## Run

With Python 3.11+:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
HOME_INTERNAL_API_SECRET=replace-me home-internal-api
```

By default the server binds to `127.0.0.1:3010`.

For LAN use, set:

```bash
HOME_INTERNAL_API_BIND_HOST=192.168.11.12
```

or another LAN address assigned to `home-server`.

## Docker

Docker でも動かせます。

ただしこの API は `home-server` 自身の状態を読むので、通常の Web API コンテナより host mount が必要です。

- Docker container 状態確認: `/var/run/docker.sock`
- `systemd` service 状態確認: host の system bus socket
- host uptime, memory, load, thermal: host の `/proc` と `/sys`
- host disk usage: host filesystem mount

Files:

- [`Dockerfile`](/Users/jagashira/work/github.com/Jagashira/home-internal-api/Dockerfile)
- [`docker-compose.yml`](/Users/jagashira/work/github.com/Jagashira/home-internal-api/docker-compose.yml)

Example:

```bash
docker compose up -d --build
```

`make` でも同じ運用ができます。

```bash
make up
make logs
make down
```

Compose example uses these mounts:

- `/:/host:ro`
- `/var/run/docker.sock:/var/run/docker.sock`
- `/run/dbus/system_bus_socket:/host/run/dbus/system_bus_socket`

And these environment values:

- `HOME_INTERNAL_API_ROOT_DISK_PATH=/host`
- `HOME_INTERNAL_API_DATA_DISK_PATH=/host/srv/home-data`
- `HOME_INTERNAL_API_PROC_PATH=/host/proc`
- `HOME_INTERNAL_API_SYS_PATH=/host/sys`
- `DBUS_SYSTEM_BUS_ADDRESS=unix:path=/host/run/dbus/system_bus_socket`

Important limitation:

- `systemctl` status from inside a container depends on access to the host D-Bus socket
- if the host uses a different socket path or tighter policy, service checks may return `unknown`
- in that case Docker status and host metrics still continue to work independently

Recommended deployment for real monitoring is still host `systemd`, because this API monitors the host itself.

## Tests

```bash
python3 -m unittest discover -s tests -v
```
