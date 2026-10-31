import asyncio
import time
from dataclasses import dataclass

import asyncpg

from app.config import settings


@dataclass
class NodeStatus:
    host: str
    role: str | None
    ok: bool
    latency_ms: float | None
    replication_lag_ms: float | None
    error: str | None


_pools: dict[str, asyncpg.Pool] = {}


async def init_pools() -> None:
    for host in settings.all_hosts:
        if host in _pools:
            continue
        _pools[host] = await asyncpg.create_pool(
            host=host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            database=settings.db_name,
            min_size=1,
            max_size=5,
            command_timeout=10,
        )


async def close_pools() -> None:
    for pool in _pools.values():
        await pool.close()
    _pools.clear()


def _role_for_host(host: str) -> str:
    if host == settings.db_primary:
        return "primary"
    return "replica"


async def ping_node(host: str) -> NodeStatus:
    pool = _pools.get(host)
    role = _role_for_host(host)
    if pool is None:
        return NodeStatus(
            host=host,
            role=role,
            ok=False,
            latency_ms=None,
            replication_lag_ms=None,
            error="pool not initialized",
        )

    started = time.perf_counter()
    try:
        async with pool.acquire() as conn:
            in_recovery = await conn.fetchval("SELECT pg_is_in_recovery()")
            lag_ms = None
            if in_recovery:
                lag_ms = await conn.fetchval(
                    """
                    SELECT CASE
                        WHEN pg_last_xact_replay_timestamp() IS NULL THEN NULL
                        ELSE EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp())) * 1000
                    END
                    """
                )
            elif host != settings.db_primary:
                role = "replica_misconfigured"
            else:
                role = "primary"

            if in_recovery and host == settings.db_primary:
                role = "primary_misconfigured"

            await conn.fetchval("SELECT 1")

        latency_ms = (time.perf_counter() - started) * 1000
        return NodeStatus(
            host=host,
            role=role,
            ok=True,
            latency_ms=round(latency_ms, 2),
            replication_lag_ms=round(float(lag_ms), 2) if lag_ms is not None else None,
            error=None,
        )
    except Exception as exc:
        return NodeStatus(
            host=host,
            role=role,
            ok=False,
            latency_ms=None,
            replication_lag_ms=None,
            error=str(exc),
        )


def node_to_dict(node: NodeStatus) -> dict:
    return {
        "host": node.host,
        "role": node.role,
        "ok": node.ok,
        "latency_ms": node.latency_ms,
        "replication_lag_ms": node.replication_lag_ms,
        "error": node.error,
    }


async def ping_all_nodes() -> list[NodeStatus]:
    tasks = [ping_node(host) for host in settings.all_hosts]
    return list(await asyncio.gather(*tasks))
