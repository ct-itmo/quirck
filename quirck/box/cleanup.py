#!/usr/bin/env python3
"""
Utility script to cleanup inactive lab instances.

This script can be run as a cron job or scheduled task to automatically
stop instances based on various criteria:
- Maximum runtime
- Inactivity (no recent VPN connections)
- Low traffic throughput

Usage:
    python -m quirck.box.cleanup [OPTIONS]

Examples:
    # Dry run with default settings
    python -m quirck.box.cleanup --dry-run

    # Stop instances running longer than 24 hours
    python -m quirck.box.cleanup --max-runtime 1440

    # Stop instances inactive for 60+ minutes (if also older than 90 min)
    python -m quirck.box.cleanup --inactive-for 90 --disconnected 60 --low-traffic 60

"""

import argparse
import asyncio
import logging

from sqlalchemy.ext.asyncio import async_sessionmaker

from quirck.box.docker import find_active_dockers, find_instances_to_reap, stop, update_client_stats
from quirck.box.exception import DockerConflict
from quirck.db.engine import get_engine
from quirck.core.config import DATABASE_URL

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser(
        description="Cleanup inactive lab instances based on runtime and activity"
    )
    parser.add_argument(
        '--max-runtime',
        type=int,
        default=24 * 60,
        help='Maximum runtime in minutes before forced reaping (default: 1440 = 24h, set to 0 to disable)'
    )
    parser.add_argument(
        '--inactive-for',
        type=int,
        default=90,
        help='Minimum runtime in minutes before checking inactivity criteria (default: 90)'
    )
    parser.add_argument(
        '--disconnected',
        type=int,
        default=60,
        help='Minutes without VPN connections to mark as inactive (default: 60, set to 0 to disable)'
    )
    parser.add_argument(
        '--low-traffic',
        type=int,
        default=60,
        help='Minutes of low traffic (<1KB/min) to mark as inactive (default: 60, set to 0 to disable)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Only check for inactive instances without stopping them'
    )

    args = parser.parse_args()

    # Convert 0 to None to disable criteria
    max_runtime = args.max_runtime if args.max_runtime > 0 else None
    disconnected = args.disconnected if args.disconnected > 0 else None
    low_traffic = args.low_traffic if args.low_traffic > 0 else None

    logger.info(
        "Starting cleanup: max_runtime=%s min, inactive_for=%s min, disconnected=%s min, low_traffic=%s min, dry_run=%s",
        max_runtime or "disabled",
        args.inactive_for,
        disconnected or "disabled",
        low_traffic or "disabled",
        args.dry_run
    )

    # Create database session factory
    engine = get_engine(DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as session:
            ready_containers = await find_active_dockers(session)
            for docker in ready_containers:
                await update_client_stats(session, docker)

            # Find instances to reap
            user_ids_to_reap = await find_instances_to_reap(
                session,
                reap_older_than_minutes=max_runtime,
                reap_disconnected_for_minutes=disconnected,
                reap_low_traffic_for_minutes=low_traffic,
                reap_inactive_if_older=args.inactive_for
            )

            if not user_ids_to_reap:
                logger.info("No instances found to reap")
                return

            logger.info("Found %d instances to reap: %s", len(user_ids_to_reap), user_ids_to_reap)

            if args.dry_run:
                logger.info("Dry run mode - not stopping instances")
                return

            # Stop instances
            stopped_count = 0
            failed_count = 0

            for user_id in user_ids_to_reap:
                try:
                    # Create new session for each stop operation
                    async with session_factory() as stop_session:
                        await stop(stop_session, user_id)
                        stopped_count += 1
                        logger.info("Successfully stopped instance for user %d", user_id)
                except DockerConflict:
                    logger.warning("Could not stop user %d: container state conflict", user_id)
                    failed_count += 1
                except Exception as e:
                    logger.error("Error stopping user %d: %s", user_id, e, exc_info=True)
                    failed_count += 1

            logger.info(
                "Cleanup complete: stopped %d instances, failed %d",
                stopped_count,
                failed_count
            )
    finally:
        await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
