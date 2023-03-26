from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ContainerMeta:
    name: str
    image: str
    # We can define MAC address for each interface
    networks: dict[str, str | None]
    bridge: bool = False
    vpn: bool = False
    mem_limit: int = 64 * 1024 * 1024
    ipv6_forwarding: bool = True  # disabling this allows RA
    volumes: dict[str, str] = field(default_factory=dict)  # host path to container path
    environment: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class NetworkMeta:
    name: str


@dataclass(frozen=True)
class Deployment:
    containers: list[ContainerMeta]
    networks: list[NetworkMeta]


__all__ = ["ContainerMeta", "Deployment", "NetworkMeta"]
