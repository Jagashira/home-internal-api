from __future__ import annotations

import os
from dataclasses import dataclass


def _split_csv(value: str, *, default: list[str]) -> list[str]:
    parts = [item.strip() for item in value.split(",")]
    return [item for item in parts if item] or default


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    bind_host: str
    internal_api_secret: str
    service_timeout_seconds: float
    docker_timeout_seconds: float
    host_timeout_seconds: float
    monitored_services: list[str]
    monitored_containers: list[str]
    data_disk_path: str
    root_disk_path: str
    proc_path: str
    sys_path: str
    docker_socket: str
    dbus_system_bus_address: str | None

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            host=os.getenv("HOME_INTERNAL_API_HOSTNAME", os.uname().nodename),
            port=int(os.getenv("HOME_INTERNAL_API_PORT", "3010")),
            bind_host=os.getenv("HOME_INTERNAL_API_BIND_HOST", "127.0.0.1"),
            internal_api_secret=os.getenv("HOME_INTERNAL_API_SECRET", ""),
            service_timeout_seconds=float(os.getenv("HOME_INTERNAL_API_SERVICE_TIMEOUT", "3")),
            docker_timeout_seconds=float(os.getenv("HOME_INTERNAL_API_DOCKER_TIMEOUT", "3")),
            host_timeout_seconds=float(os.getenv("HOME_INTERNAL_API_HOST_TIMEOUT", "3")),
            monitored_services=_split_csv(
                os.getenv("HOME_INTERNAL_API_MONITORED_SERVICES", "glances,home-platform,docker"),
                default=["glances", "home-platform", "docker"],
            ),
            monitored_containers=_split_csv(
                os.getenv(
                    "HOME_INTERNAL_API_MONITORED_CONTAINERS",
                    "news-aggregator,immich_server,immich_machine_learning,immich_postgres,immich_redis",
                ),
                default=[
                    "news-aggregator",
                    "immich_server",
                    "immich_machine_learning",
                    "immich_postgres",
                    "immich_redis",
                ],
            ),
            data_disk_path=os.getenv("HOME_INTERNAL_API_DATA_DISK_PATH", "/srv/home-data"),
            root_disk_path=os.getenv("HOME_INTERNAL_API_ROOT_DISK_PATH", "/"),
            proc_path=os.getenv("HOME_INTERNAL_API_PROC_PATH", "/proc"),
            sys_path=os.getenv("HOME_INTERNAL_API_SYS_PATH", "/sys"),
            docker_socket=os.getenv("DOCKER_HOST", "unix:///var/run/docker.sock"),
            dbus_system_bus_address=os.getenv("DBUS_SYSTEM_BUS_ADDRESS") or None,
        )
