from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ServiceState = Literal["active", "inactive", "failed", "missing", "unknown"]
ContainerState = Literal["running", "stopped", "missing", "unknown"]


@dataclass(frozen=True)
class ServiceItem:
    name: str
    state: ServiceState


@dataclass(frozen=True)
class ContainerItem:
    name: str
    state: ContainerState
