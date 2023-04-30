import logging
from typing import Any

import aiodocker
from aiodocker.containers import DockerContainer
from aiodocker.networks import DockerNetwork
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from quirck.box.exception import DockerConflict
from quirck.box.meta import ContainerMeta, Deployment, NetworkMeta
from quirck.box.model import DockerMeta, DockerState
from quirck.box.vpn import generate_vpn
from quirck.core import config

logger = logging.getLogger(__name__)


def get_full_object_name(user_id: int, name: str) -> str:
    return f"quirck-{config.APP_MODULE}-{user_id}-{name}"


async def create_network(user_id: int, network: NetworkMeta) -> DockerNetwork:
    async with aiodocker.Docker() as client:
        return await client.networks.create({
            "Name": get_full_object_name(user_id, network.name),
            "Driver": "nsychev/katharanp:amd64",
            "IPAM": {"Driver": "null"},
            "Labels": {"user_id": f"{user_id}"},
            "CheckDuplicate": True
        })


async def run_container(meta: DockerMeta, container: ContainerMeta) -> DockerContainer:
    environment: dict[str, Any] = {"USER_ID": meta.user_id}
    environment.update(container.environment)

    options: dict[str, Any] = {}
    host_options: dict[str, Any] = {}

    if container.vpn:
        if meta.vpn is None:
            raise ValueError("No VPN configuration available")

        environment.update(meta.vpn)

        host_options["PortBindings"] = {"1194/tcp": [{"HostPort": str(meta.port)}]}

    if container.volumes:
        host_options["Binds"] = [
            f"{host_path}:{container_path}"
            for host_path, container_path in container.volumes.items()
        ]

    # We should attach a container to one and only one network at creation time
    if container.bridge:
        # If this container should be bridged to host, we choose bridge
        host_options["NetworkMode"] = "bridge"
        networks = container.networks
    else:
        # Otherwise, we choose any of required networks
        first_net, *other_tuples = container.networks.items()

        first_net_name, first_net_mac = first_net
        host_options["NetworkMode"] = get_full_object_name(meta.user_id, first_net_name)
        if first_net_mac:
            options["MacAddress"] = first_net_mac
        options["NetworkingConfig"] = {
            "EndpointsConfig": {
                get_full_object_name(meta.user_id, first_net_name): {}
            }
        }

        networks = dict(other_tuples)

    sysctls = {
        "net.ipv6.conf.all.disable_ipv6": "0"
    }

    if container.ipv6_forwarding:
        sysctls["net.ipv6.conf.all.forwarding"] = "1"

    async with aiodocker.Docker() as client:
        box = await client.containers.create(
            name=get_full_object_name(meta.user_id, container.name),
            config={
                "AttachStdout": False,
                "AttachStderr": False,
                "Image": container.image,
                "Env": [
                    f"{key}={value}"
                    for key, value in environment.items()
                ],
                "Labels": {
                    "user_id": f"{meta.user_id}",
                    "chapter": meta.chapter
                },
                "HostConfig": {
                    "CapAdd": ["NET_ADMIN", "NET_RAW"],
                    "Memory": container.mem_limit,
                    "Sysctls": sysctls,
                    **host_options
                },
                **options
            }
        )

        for network_name, mac_address in networks.items():
            network = await client.networks.get(get_full_object_name(meta.user_id, network_name))
            await network.connect({
                "Container": box.id,
                "EndpointConfig": {
                    "MacAddress": mac_address,
                    "DriverOpts": {"org.kathara.katharanp.mac": mac_address}
                } if mac_address else {}
            })

        await box.start()

    return box


async def lock_meta(session: AsyncSession, user_id: int, chapter: str | None, assert_chapter: bool = False) -> DockerMeta:
    meta = (await session.scalars(
        select(DockerMeta)
            .filter(DockerMeta.user_id == user_id)
            .with_for_update()
    )).one_or_none()

    if assert_chapter and (meta is None or meta.chapter != chapter):
        # Close the transaction
        await session.rollback()
        raise DockerConflict()

    if meta is None:
        meta = DockerMeta(user_id=user_id, chapter=chapter, state=DockerState.IN_PROGRESS)
        session.add(meta)
        await session.commit()

        return meta

    if meta.state == DockerState.IN_PROGRESS:
        await session.rollback()
        raise DockerConflict()

    meta.chapter = chapter
    meta.state = DockerState.IN_PROGRESS

    await session.commit()
    
    return meta


async def clean(user_id: int) -> None:
    async with aiodocker.Docker() as client:
        containers = await client.containers.list(
            all=True,
            filters={"label": [f"user_id={user_id}"]}
        )

        for container in containers:
            await container.delete(force=True, v=True)

        for network in await client.networks.list(
                filters={"label": f"user_id={user_id}"}
            ):
            await DockerNetwork(client, network["Id"]).delete()


async def launch(session: AsyncSession, meta: DockerMeta, deployment: Deployment) -> None:
    """Expects that lock is taken elsewhere."""

    assert(meta.state == DockerState.IN_PROGRESS)

    await clean(meta.user_id)

    if meta.vpn is None:
        meta.vpn = await generate_vpn(meta.user_id, meta.port)
        await session.commit()

    for network in deployment.networks:
        await create_network(meta.user_id, network)
    
    for container in deployment.containers:
        await run_container(meta, container)
    
    meta.state = DockerState.READY
    await session.commit()


async def stop(session: AsyncSession, user_id: int) -> None:
    meta = await lock_meta(session, user_id, None)

    await clean(user_id)

    meta.state = DockerState.DISABLED
    await session.commit()


async def stop_all(session: AsyncSession, chapter: str | None = None) -> None:
    query = select(DockerMeta).where(DockerMeta.state == DockerState.READY)
    if chapter:
        query = query.where(DockerMeta.chapter == chapter)

    candidates = (await session.scalars(query)).all()

    for candidate in candidates:
        try:
            await stop(session, candidate.user_id)
        except DockerConflict:
            logger.warning("Could not stop %s due to lock", candidate.user_id)


__all__ = ["launch", "stop", "stop_all"]
