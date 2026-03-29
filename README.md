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

Initial monitored targets:

- services: `glances`, `home-platform`, `home-internal-api`, `docker`
- containers: `news-aggregator`, `immich_server`, `immich_machine_learning`, `immich_postgres`, `immich_redis`

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
    "news-aggregator": "running",
    "immich_server": "running",
    "immich_machine_learning": "running",
    "immich_postgres": "running",
    "immich_redis": "running"
  },
  "summary": {
    "servicesOk": 4,
    "servicesTotal": 4,
    "containersRunning": 5,
    "containersTotal": 5
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
    { "name": "news-aggregator", "state": "running" },
    { "name": "immich_server", "state": "running" },
    { "name": "immich_machine_learning", "state": "running" }
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

## Home Assistant Example

```yaml
rest:
  - resource: "http://192.168.11.12:3010/api/status/summary"
    scan_interval: 60
    headers:
      x-internal-api-secret: !secret home_internal_api_secret
    sensor:
      - name: "Internal Services OK"
        value_template: "{{ value_json.summary.servicesOk }}"
      - name: "Internal Containers Running"
        value_template: "{{ value_json.summary.containersRunning }}"
      - name: "Glances State"
        value_template: "{{ value_json.services.glances }}"
      - name: "Home Platform State"
        value_template: "{{ value_json.services['home-platform'] }}"
      - name: "News Aggregator State"
        value_template: "{{ value_json.containers['news-aggregator'] }}"

template:
  - binary_sensor:
      - name: "Glances Healthy"
        state: "{{ states('sensor.glances_state') == 'active' }}"
      - name: "News Aggregator Healthy"
        state: "{{ states('sensor.news_aggregator_state') == 'running' }}"
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

## systemd + Docker Compose

`home-server` で常時起動したい場合は、Docker Compose を `systemd` で管理できます。

Unit file:

- [`deploy/systemd/home-internal-api.service`](/Users/jagashira/work/github.com/Jagashira/home-internal-api/deploy/systemd/home-internal-api.service)

Recommended layout on `home-server`:

- app directory: `/opt/home-internal-api`
- working tree includes `docker-compose.yml`, `Dockerfile`, `Makefile`
- copy [`.env.example`](/Users/jagashira/work/github.com/Jagashira/home-internal-api/.env.example) to `.env` and set the real secret before enable

Install example:

```bash
sudo mkdir -p /opt
sudo rsync -a ./ /opt/home-internal-api/
cd /opt/home-internal-api
cp .env.example .env
$EDITOR .env
sudo make install-systemd
sudo systemctl enable --now home-internal-api.service
```

Useful commands:

```bash
sudo systemctl status home-internal-api.service
sudo journalctl -u home-internal-api.service -f
sudo systemctl restart home-internal-api.service
```

The service runs:

- `make up` on start
- `make down` on stop

If your host uses a different `make` or `docker compose` path, update the unit file accordingly.

## systemd Example

```ini
[Unit]
Description=home-internal-api
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/home-internal-api
EnvironmentFile=/opt/home-internal-api/.env
ExecStart=/opt/home-internal-api/.venv/bin/home-internal-api
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```
