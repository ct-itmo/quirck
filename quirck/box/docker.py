import logging
from datetime import datetime, timezone, timedelta
from typing import Any

import aiodocker
from aiodocker.containers import DockerContainer
from aiodocker.execs import Exec
from aiodocker.networks import DockerNetwork
from attr import dataclass
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from quirck.box.exception import DockerConflict
from quirck.box.meta import ContainerMeta, Deployment, NetworkMeta
from quirck.box.model import DockerClientStats, DockerMeta, DockerState
from quirck.box.vpn import generate_vpn
from quirck.core import config

logger = logging.getLogger(__name__)


def get_full_object_name(user_id: int, name: str) -> str:
    return f"quirck-{config.APP_MODULE}-{user_id}-{name}"


async def create_network(user_id: int, network: NetworkMeta) -> DockerNetwork:
    async with aiodocker.Docker() as client:
        return await client.networks.create({
            "Name": get_full_object_name(user_id, network.name),
            "Driver": "kathara/katharanp:amd64",
            "IPAM": {"Driver": "null"},
            "Labels": {"user_id": f"{user_id}"},
            "CheckDuplicate": True,
            "EnableIPv6": True,
        })


def kathara_endpoint_config(mac_address: str | None) -> dict[str, Any]:
    config = {
        "DriverOpts": {
            "com.docker.network.endpoint.sysctls": "net.ipv6.conf.IFNAME.disable_ipv6=0"
        }
    }

    if mac_address is not None:
        config["DriverOpts"]["kathara.mac_addr"] = mac_address

    return config


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
        options["NetworkingConfig"] = {
            "EndpointsConfig": {
                "bridge": {
                    "DriverOpts": {
                        "com.docker.network.endpoint.ifname": "ext"
                    }
                }
            }
        }

        networks = container.networks
    else:
        # Otherwise, we choose any of required networks
        first_net, *other_tuples = container.networks.items()

        first_net_name, first_net_mac = first_net
        host_options["NetworkMode"] = get_full_object_name(meta.user_id, first_net_name)
        options["NetworkingConfig"] = {
            "EndpointsConfig": {
                get_full_object_name(meta.user_id, first_net_name): kathara_endpoint_config(first_net_mac)
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
                "EndpointConfig": kathara_endpoint_config(mac_address)
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

    assert meta.state == DockerState.IN_PROGRESS

    await clean(meta.user_id)

    if meta.vpn is None:
        meta.vpn = await generate_vpn(meta.user_id, meta.port)
        await session.commit()

    for network in deployment.networks:
        await create_network(meta.user_id, network)

    for container in deployment.containers:
        await run_container(meta, container)

    meta.state = DockerState.READY
    meta.changed_at = datetime.now(timezone.utc)
    await session.commit()


async def stop_locked(session: AsyncSession, meta: DockerMeta) -> None:
    """Expects that lock is taken elsewhere."""

    assert meta.state == DockerState.IN_PROGRESS

    await clean(meta.user_id)

    meta.state = DockerState.DISABLED
    meta.changed_at = datetime.now(timezone.utc)
    await session.commit()


async def stop(session: AsyncSession, user_id: int) -> None:
    meta = await lock_meta(session, user_id, None)

    await stop_locked(session, meta)


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


class ExecResult:
    exit_code: int
    stdout: bytes = b""
    stderr: bytes = b""


async def exec_command(execution: Exec) -> ExecResult:
    result = ExecResult()

    async with execution.start(detach=False) as stream:
        while True:
            msg = await stream.read_out()
            if msg is None:
                break
            if msg.stream == 1:
                result.stdout += msg.data
            elif msg.stream == 2:
                result.stderr += msg.data
            else:
                raise KeyError(f"Unknown stream type: {msg.stream}")

    inspect = await execution.inspect()
    result.exit_code = inspect["ExitCode"]

    return result


async def find_active_dockers(session: AsyncSession) -> list[DockerMeta]:
    return (await session.scalars(
        select(DockerMeta).where(DockerMeta.state == DockerState.READY)
    )).all()


@dataclass
class ClientStatPoint:
    client_ip: str
    connected_at: datetime
    bytes_recv: int
    bytes_sent: int


async def update_client_stats(session: AsyncSession, docker: DockerMeta) -> None:
    """
    Update the client statistics for the VPN container of a given user.
    """
    async with aiodocker.Docker() as client:
        containers = await client.containers.list(
            filters={
                "name": [get_full_object_name(docker.user_id, "vpn")]
            }
        )

        if not containers:
            return

        container = containers[0]

        execution = await container.exec(["/bin/cat", "/openvpn-status"])
        result = await exec_command(execution)

        if result.exit_code != 0:
            logger.error("Failed to get VPN status for user %d: %s", docker.user_id, result.stderr.decode(errors="replace"))
            return

        lines = result.stdout.decode('utf-8').strip().split('\n')

        in_client_list = False
        client_records: list[ClientStatPoint] = []

        for line in lines:
            if line.startswith('Common Name,Real Address'):
                in_client_list = True
                continue
            elif line.startswith('ROUTING TABLE'):
                in_client_list = False
                break

            if in_client_list and line.strip():
                parts = line.split(',')
                if len(parts) >= 5:
                    client_ip = parts[1]
                    bytes_received = int(parts[2])
                    bytes_sent = int(parts[3])
                    connected_since = parts[4]

                    connected_at = datetime.strptime(connected_since, '%Y-%m-%d %H:%M:%S')
                    connected_at = connected_at.replace(tzinfo=timezone.utc)

                    client_records.append(
                        ClientStatPoint(
                            client_ip=client_ip,
                            connected_at=connected_at,
                            bytes_recv=bytes_received,
                            bytes_sent=bytes_sent
                        )
                    )
                else:
                    logger.warning("Unexpected line format in VPN status for user %d: %s", docker.user_id, line)

        for record in client_records:
            stats = DockerClientStats(
                docker_id=docker.port,
                client_ip=record.client_ip,
                connected_at=record.connected_at,
                bytes_recv=record.bytes_recv,
                bytes_sent=record.bytes_sent
            )
            session.add(stats)

        cutoff_time = datetime.now(timezone.utc) - timedelta(days=7)
        await session.execute(
            delete(DockerClientStats).where(
                DockerClientStats.docker_id == docker.port,
                DockerClientStats.recorded_at < cutoff_time
            )
        )

        await session.commit()


async def find_instances_to_reap(
    session: AsyncSession,
    reap_older_than_minutes: int | None = 24 * 60,
    reap_disconnected_for_minutes: int | None = 60,
    reap_low_traffic_for_minutes: int | None = 60,
    reap_inactive_if_older: int = 90,
) -> list[int]:
    """
    Find containers if one of following criterias is true:

    Criteria 1. The container has been running for more than `reap_older_than_minutes` minutes (if set).

    Criteria 2. The container has been running for more than `reap_inactive_if_older` minutes and either:
     - no clients connected in last `reap_disconnected_for_minutes` minutes (if set)
     - in last `reap_low_traffic_for_minutes` minutes (if set) there was low traffic throughput

    Low traffic means that there is no client that sent plus received at least 1 KB/min for each minute for the last `reap_low_traffic_for_minutes` minutes.
    If there are not enough data points (e.g. 5-minute frame), calculate the average.

    For each container scheduled to reap, log the reason.
    """

    to_reap: list[int] = []
    now = datetime.now(timezone.utc)

    # Get all READY containers
    ready_containers = await find_active_dockers(session)

    for docker in ready_containers:
        running_minutes = (now - docker.changed_at).total_seconds() / 60

        # Criteria 1: Running too long
        if reap_older_than_minutes is not None and running_minutes > reap_older_than_minutes:
            logger.info(
                "Reaping container for user %d: running for %.1f minutes (threshold: %d)",
                docker.user_id, running_minutes, reap_older_than_minutes
            )
            to_reap.append(docker.user_id)
            continue

        # Criteria 2: Old enough and inactive
        if running_minutes > reap_inactive_if_older:
            should_reap = False
            reason = ""

            # Check disconnection criteria
            if reap_disconnected_for_minutes is not None:
                cutoff_time = now - timedelta(minutes=reap_disconnected_for_minutes)
                recent_stats = (await session.scalars(
                    select(DockerClientStats)
                    .where(
                        DockerClientStats.docker_id == docker.port,
                        DockerClientStats.recorded_at >= cutoff_time
                    )
                )).all()

                if not recent_stats:
                    should_reap = True
                    reason = f"no clients connected in last {reap_disconnected_for_minutes} minutes"

            # Check low traffic criteria (only if not already marked for reaping)
            if not should_reap and reap_low_traffic_for_minutes is not None:
                cutoff_time = now - timedelta(minutes=reap_low_traffic_for_minutes)
                traffic_stats = (await session.scalars(
                    select(DockerClientStats)
                    .where(
                        DockerClientStats.docker_id == docker.port,
                        DockerClientStats.recorded_at >= cutoff_time
                    )
                    .order_by(DockerClientStats.recorded_at)
                )).all()

                if not traffic_stats:
                    should_reap = True
                    reason = f"no traffic data in last {reap_low_traffic_for_minutes} minutes"
                else:
                    # Group by (client_ip, connected_at) to identify unique sessions
                    sessions: dict[tuple[str, datetime], list[DockerClientStats]] = {}
                    for stat in traffic_stats:
                        key = (stat.client_ip, stat.connected_at)
                        if key not in sessions:
                            sessions[key] = []
                        sessions[key].append(stat)

                    has_active_client = False
                    for session_stats in sessions.values():
                        if len(session_stats) >= 2:
                            # Multiple data points - calculate throughput between first and last
                            first = session_stats[0]
                            last = session_stats[-1]

                            time_diff_minutes = (last.recorded_at - first.recorded_at).total_seconds() / 60
                            if time_diff_minutes > 0:
                                total_bytes = (
                                    (last.bytes_recv - first.bytes_recv) +
                                    (last.bytes_sent - first.bytes_sent)
                                )
                                bytes_per_minute = total_bytes / time_diff_minutes

                                # Threshold: 1 KB/min = 1024 bytes/min
                                if bytes_per_minute >= 1024:
                                    has_active_client = True
                                    break
                        else:
                            # Single data point - calculate average since connection
                            stat = session_stats[0]
                            time_since_connect_minutes = (stat.recorded_at - stat.connected_at).total_seconds() / 60
                            if time_since_connect_minutes > 0:
                                total_bytes = stat.bytes_recv + stat.bytes_sent
                                bytes_per_minute = total_bytes / time_since_connect_minutes

                                if bytes_per_minute >= 1024:
                                    has_active_client = True
                                    break

                    if not has_active_client:
                        should_reap = True
                        reason = f"low traffic in last {reap_low_traffic_for_minutes} minutes"

            if should_reap:
                logger.info(
                    "Reaping container for user %d: running for %.1f minutes (inactive threshold: %d), %s",
                    docker.user_id, running_minutes, reap_inactive_if_older, reason
                )
                to_reap.append(docker.user_id)

    return to_reap


__all__ = ["launch", "stop", "stop_all", "find_active_dockers", "find_instances_to_reap", "update_client_stats"]
