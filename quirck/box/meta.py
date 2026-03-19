from dataclasses import dataclass, field


@dataclass(frozen=True)
class ContainerNetworkMeta:
    network_name: str
    mac_address: str | None = None
    # net.ipv6.conf.IFNAME.disable_ipv6=0 is always added
    sysctls: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ContainerMeta:
    name: str
    image: str
    networks: list[ContainerNetworkMeta]
    bridge: bool = False
    vpn: bool = False
    mem_limit: int = 64 * 1024 * 1024
    ipv6_forwarding: bool = True  # disabling this allows RA
    volumes: dict[str, str] = field(default_factory=dict)  # host path to container path
    environment: dict[str, str] = field(default_factory=dict)

    @staticmethod
    def make_vpn(user_id: int, network_names: list[str]) -> "ContainerMeta":
        """Produces a configuration for VPN container. First network is going to be default, others are need to be specified by UV_NETWORK client environment variable."""
        padded_id = f"00000000{user_id}"[-8:]
        mac_prefix = (
            "06:"
            + ":".join(padded_id[i : i + 2] for i in range(0, len(padded_id), 2))
            + ":"
        )

        networks = [
            ContainerNetworkMeta(
                network_name=network_name,
                mac_address=f"{mac_prefix}{idx:02d}",
            )
            for idx, network_name in enumerate(network_names)
        ]

        environment = {
            "NETWORK_LIST": " ".join(network_names),
            "NETWORK_DEFAULT": network_names[0],
        }

        for network in networks:
            environment[f"NETWORK_HWADDR_{network.network_name}"] = (
                network.mac_address or ""
            )

        return ContainerMeta(
            name="vpn",
            image="ct-itmo/quirck-relay",
            networks=networks,
            bridge=True,
            vpn=True,
            environment=environment,
        )


@dataclass(frozen=True)
class NetworkMeta:
    name: str


@dataclass(frozen=True)
class Deployment:
    containers: list[ContainerMeta]
    networks: list[NetworkMeta]


__all__ = ["ContainerMeta", "Deployment", "NetworkMeta", "ContainerNetworkMeta"]
