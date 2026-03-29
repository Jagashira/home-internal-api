from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import Settings
from .models import ContainerItem, ContainerState, ServiceItem, ServiceState


def iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _run_command(
    command: list[str],
    timeout: float,
    *,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            check=False,
            env=env,
            text=True,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError):
        return None


def normalize_service_state(value: str | None) -> ServiceState:
    state = (value or "").strip().lower()
    if state == "active":
        return "active"
    if state == "inactive":
        return "inactive"
    if state == "failed":
        return "failed"
    if state in {"not-found", "missing"}:
        return "missing"
    return "unknown"


def normalize_container_state(value: str | None) -> ContainerState:
    state = (value or "").strip().lower()
    if state == "running":
        return "running"
    if state in {"exited", "dead", "created", "paused", "restarting", "stopped"}:
        return "stopped"
    if state in {"missing", "not-found"}:
        return "missing"
    return "unknown"


def collect_services(settings: Settings) -> dict[str, Any]:
    updated_at = iso_now()
    items: list[ServiceItem] = []
    systemctl_path = shutil.which("systemctl")

    for name in settings.monitored_services:
        if not systemctl_path:
            items.append(ServiceItem(name=name, state="unknown"))
            continue

        env = os.environ.copy()
        if settings.dbus_system_bus_address:
            env["DBUS_SYSTEM_BUS_ADDRESS"] = settings.dbus_system_bus_address

        result = _run_command(
            [systemctl_path, "show", name, "--property=LoadState,ActiveState", "--value"],
            settings.service_timeout_seconds,
            env=env,
        )
        if result is None:
            items.append(ServiceItem(name=name, state="unknown"))
            continue

        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        load_state = lines[0] if len(lines) > 0 else ""
        active_state = lines[1] if len(lines) > 1 else ""

        if load_state == "not-found":
            state: ServiceState = "missing"
        else:
            state = normalize_service_state(active_state)

        items.append(ServiceItem(name=name, state=state))

    return {
        "ok": True,
        "updatedAt": updated_at,
        "items": [asdict(item) for item in items],
    }


def collect_containers(settings: Settings) -> dict[str, Any]:
    updated_at = iso_now()
    items: list[ContainerItem] = []
    docker_path = shutil.which("docker")

    if not docker_path:
        items = [ContainerItem(name=name, state="unknown") for name in settings.monitored_containers]
        return {"ok": True, "updatedAt": updated_at, "items": [asdict(item) for item in items]}

    for name in settings.monitored_containers:
        result = _run_command(
            [docker_path, "inspect", "--format", "{{.State.Status}}", name],
            settings.docker_timeout_seconds,
            env={**os.environ.copy(), "DOCKER_HOST": settings.docker_socket},
        )
        if result is None:
            items.append(ContainerItem(name=name, state="unknown"))
            continue

        stderr = (result.stderr or "").lower()
        if result.returncode != 0 and "no such object" in stderr:
            items.append(ContainerItem(name=name, state="missing"))
            continue

        if result.returncode != 0:
            items.append(ContainerItem(name=name, state="unknown"))
            continue

        items.append(ContainerItem(name=name, state=normalize_container_state(result.stdout)))

    return {
        "ok": True,
        "updatedAt": updated_at,
        "items": [asdict(item) for item in items],
    }

def _read_cpu_temperature_from(sys_path: str) -> float | None:
    thermal_root = Path(sys_path) / "class" / "thermal"
    if not thermal_root.exists():
        return None

    for candidate in thermal_root.glob("thermal_zone*/temp"):
        try:
            raw = candidate.read_text(encoding="utf-8").strip()
            value = float(raw)
        except (OSError, ValueError):
            continue
        return round(value / 1000.0, 1) if value > 1000 else round(value, 1)

    return None


def _disk_usage_percent(path: str) -> tuple[float | None, int | None]:
    try:
        usage = shutil.disk_usage(path)
    except FileNotFoundError:
        return None, None

    total = usage.total
    if total <= 0:
        return 0.0, usage.free

    used_percent = round(((total - usage.free) / total) * 100, 1)
    return used_percent, usage.free

def _memory_snapshot_from(proc_path: str) -> tuple[float | None, int | None]:
    try:
        with open(Path(proc_path) / "meminfo", "r", encoding="utf-8") as handle:
            values: dict[str, int] = {}
            for line in handle:
                key, raw_value = line.split(":", 1)
                number = int(raw_value.strip().split()[0]) * 1024
                values[key] = number
    except (OSError, ValueError):
        return None, None

    total = values.get("MemTotal")
    available = values.get("MemAvailable")
    if not total or available is None:
        return None, None

    used_percent = round(((total - available) / total) * 100, 1)
    return used_percent, available


def _load_average_from(proc_path: str) -> tuple[float | None, float | None, float | None]:
    try:
        with open(Path(proc_path) / "loadavg", "r", encoding="utf-8") as handle:
            values = handle.read().split()
            return float(values[0]), float(values[1]), float(values[2])
    except (OSError, ValueError, IndexError):
        return None, None, None


def collect_host(settings: Settings) -> dict[str, Any]:
    updated_at = iso_now()
    load1, load5, load15 = _load_average_from(settings.proc_path)
    memory_used_percent, memory_free_bytes = _memory_snapshot_from(settings.proc_path)
    root_disk_used_percent, _ = _disk_usage_percent(settings.root_disk_path)
    data_disk_used_percent, data_disk_free_bytes = _disk_usage_percent(settings.data_disk_path)
    cpu_temperature = _read_cpu_temperature_from(settings.sys_path)

    response = {
        "ok": True,
        "updatedAt": updated_at,
        "host": {
            "uptimeSeconds": _read_uptime_seconds_from(settings.proc_path),
            "load1": round(load1, 2) if load1 is not None else None,
            "load5": round(load5, 2) if load5 is not None else None,
            "load15": round(load15, 2) if load15 is not None else None,
            "memoryUsedPercent": memory_used_percent,
            "memoryFreeBytes": memory_free_bytes,
            "rootDiskUsedPercent": root_disk_used_percent,
            "dataDiskUsedPercent": data_disk_used_percent,
            "dataDiskFreeBytes": data_disk_free_bytes,
            "cpuTemperatureC": cpu_temperature,
        },
    }
    return response


def _read_uptime_seconds_from(proc_path: str) -> int | None:
    try:
        with open(Path(proc_path) / "uptime", "r", encoding="utf-8") as handle:
            return int(float(handle.read().split()[0]))
    except (OSError, ValueError, IndexError):
        return None


def collect_summary(settings: Settings) -> dict[str, Any]:
    services_response = collect_services(settings)
    containers_response = collect_containers(settings)

    service_map = {item["name"]: item["state"] for item in services_response["items"]}
    container_map = {item["name"]: item["state"] for item in containers_response["items"]}

    services_ok = sum(1 for state in service_map.values() if state == "active")
    containers_running = sum(1 for state in container_map.values() if state == "running")

    return {
        "ok": True,
        "host": {
            "name": settings.host,
            "updatedAt": iso_now(),
        },
        "services": service_map,
        "containers": container_map,
        "summary": {
            "servicesOk": services_ok,
            "servicesTotal": len(service_map),
            "containersRunning": containers_running,
            "containersTotal": len(container_map),
        },
    }


def dumps_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
