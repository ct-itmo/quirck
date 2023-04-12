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

    @staticmethod
    def make_vpn(user_id: int, networks: list[str]) -> "ContainerMeta":
        """Produces a configuration for VPN container. First network is going to be default, others are need to be specified by UV_NETWORK client environment variable."""
        padded_id = f"00000000{user_id}"[-8:]
        mac_prefix = "06:" + ":".join(padded_id[i:i+2] for i in range(0, len(padded_id), 2)) + ":"

        network_macs = {
            network: f"{mac_prefix}{idx:02d}"
            for idx, network in enumerate(networks)
        }

        environment = {
            "NETWORK_LIST": " ".join(networks),
            "NETWORK_DEFAULT": networks[0]
        }

        for network, mac_address in network_macs.items():
            environment[f"NETWORK_HWADDR_{network}"] = mac_address
        
        return ContainerMeta(
            name="vpn",
            image="ct-itmo/quirck-relay",
            networks=network_macs,  # type: ignore
            bridge=True,
            vpn=True,
            environment=environment
        )



@dataclass(frozen=True)
class NetworkMeta:
    name: str


@dataclass(frozen=True)
class Deployment:
    containers: list[ContainerMeta]
    networks: list[NetworkMeta]


__all__ = ["ContainerMeta", "Deployment", "NetworkMeta"]
