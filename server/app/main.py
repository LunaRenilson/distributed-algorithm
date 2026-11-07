"""Aplicação FastAPI Principal do MC714 Tickets com Algoritmos Distribuídos.

Este módulo expõe a interface pública HTTP multithread para:
- Ordenação de Eventos (Relógio Lógico de Lamport)
- Exclusão Mútua Distribuída (Ricart-Agrawala)
- Compromisso Atômico (Two-Phase Commit - 2PC)
- Detecção de Falhas (Heartbeat Failure Detector)
"""

import asyncio
import json
import time
import urllib.error
import urllib.request
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, Field

from app import db
from app.algorithms.heartbeat import HeartbeatFailureDetector
from app.algorithms.lamport import LamportClock
from app.algorithms.ricart_agrawala import RicartAgrawalaMutex
from app.algorithms.two_phase_commit import TwoPhaseCoordinator
from app.config import settings

# Instâncias dos algoritmos gerenciadas pelo nó API Coordenador
lamport_clock = LamportClock(node_id=settings.node_id)


def _http_call_sync(method: str, url: str, data: dict | None = None, timeout: float = 3.0) -> tuple[int, dict]:
    """Executa uma requisição HTTP síncrona utilizando urllib padrão.

    Args:
        method (str): Método HTTP (GET, POST, etc.).
        url (str): URL de destino da chamada.
        data (dict | None, opcional): Dados a serem enviados no corpo como JSON.
        timeout (float, opcional): Timeout limite em segundos.

    Returns:
        tuple[int, dict]: Código de status HTTP e dicionário com resposta JSON parsed.
    """
    try:
        body = json.dumps(data).encode("utf-8") if data else None
        headers = {"Content-Type": "application/json"} if data else {}
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        return exc.code, {}
    except Exception:
        return 0, {}


async def async_http_call(method: str, url: str, data: dict | None = None, timeout: float = 3.0) -> tuple[int, dict]:
    """Envelopa a chamada síncrona _http_call_sync em um executor de threads do asyncio.

    Garante concorrência não-bloqueante no loop de eventos da FastAPI.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _http_call_sync, method, url, data, timeout)


# Callbacks para o Ricart-Agrawala do coordenador
async def send_mutex_request_to_helper(peer_host: str, ts) -> bool:
    """Dispara uma solicitação de lock distribuído (REQUEST) para um nó helper via HTTP."""
    url = f"http://{peer_host}:{settings.helper_port}/mutex/request"
    code, resp = await async_http_call("POST", url, {
        "requester_id": settings.node_id,
        "clock": ts.clock,
        "node_id": ts.node_id,
    })
    return code == 200 and bool(resp.get("granted", False))


async def send_mutex_reply_to_helper(peer_host: str) -> bool:
    """Dispara uma resposta de permissão (REPLY/OK) para um nó helper via HTTP."""
    url = f"http://{peer_host}:{settings.helper_port}/mutex/reply"
    code, _ = await async_http_call("POST", url, {"from_node": settings.node_id})
    return code == 200


mutex_coordinator = RicartAgrawalaMutex(
    node_id=settings.node_id,
    peers=settings.helper_hosts,
    clock=lamport_clock,
    send_request_fn=send_mutex_request_to_helper,
    send_reply_fn=send_mutex_reply_to_helper,
)


# Callbacks para o Two-Phase Commit (2PC)
async def tpc_prepare_participant(peer_host: str, tx_id: str, payload: dict) -> bool:
    """Emite a fase PREPARE para um participante do 2PC e retorna True se votar YES."""
    url = f"http://{peer_host}:{settings.helper_port}/tx/prepare"
    code, resp = await async_http_call("POST", url, {"tx_id": tx_id, "payload": payload}, timeout=3.0)
    return code == 200 and resp.get("vote") == "YES"


async def tpc_commit_participant(peer_host: str, tx_id: str) -> bool:
    """Emite o comando de COMMIT na fase 2 para um participante do 2PC."""
    url = f"http://{peer_host}:{settings.helper_port}/tx/commit"
    code, resp = await async_http_call("POST", url, {"tx_id": tx_id}, timeout=3.0)
    return code == 200 and bool(resp.get("committed", False))


async def tpc_abort_participant(peer_host: str, tx_id: str) -> bool:
    """Emite o comando de ABORT na fase 2 para um participante do 2PC."""
    url = f"http://{peer_host}:{settings.helper_port}/tx/abort"
    code, resp = await async_http_call("POST", url, {"tx_id": tx_id}, timeout=3.0)
    return code == 200 and bool(resp.get("aborted", False))


two_phase_coordinator = TwoPhaseCoordinator(
    coordinator_id=settings.node_id,
    participants=settings.helper_hosts,
    prepare_call=tpc_prepare_participant,
    commit_call=tpc_commit_participant,
    abort_call=tpc_abort_participant,
)


# Callback para Heartbeat de nós do cluster
async def ping_helper_or_db(node: str) -> bool:
    """Sonda a conectividade com nós de banco (PostgreSQL) ou nós helpers de computação distribuída."""
    if node in settings.all_hosts:
        st = await db.ping_node(node)
        return st.ok
    else:
        url = f"http://{node}:{settings.helper_port}/ping"
        code, _ = await async_http_call("GET", url, timeout=1.5)
        return code == 200


monitored_nodes = [*settings.all_hosts, *settings.helper_hosts]
failure_detector = HeartbeatFailureDetector(
    nodes=monitored_nodes,
    ping_fn=ping_helper_or_db,
    interval_seconds=3.0,
    timeout_seconds=2.0,
    max_missed=3,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerenciador de ciclo de vida da aplicação FastAPI para conexões e tarefas de background."""
    await db.init_pools()
    await failure_detector.start()
    yield
    await failure_detector.stop()
    await db.close_pools()


app = FastAPI(title="MC714 Distributed Tickets API", lifespan=lifespan)


# ============================================================================
# Endpoints Básicos de Saúde e Informações do Banco
# ============================================================================

@app.get("/health")
async def health():
    """Checagem rápida de liveness da API."""
    return {"status": "ok"}


@app.get("/ready")
async def ready(response: Response):
    """Verifica se todos os nós de banco primário e réplicas estão saudáveis e sincronizados."""
    nodes = await db.ping_all_nodes()
    all_ok = all(n.ok for n in nodes)
    roles_ok = (
        sum(1 for n in nodes if n.role == "primary") == 1
        and all(n.role == "replica" for n in nodes if n.host != settings.db_primary)
    )
    if not all_ok or not roles_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "ready": all_ok and roles_ok,
        "primary": settings.db_primary,
        "replicas": settings.replica_hosts,
        "nodes": [db.node_to_dict(n) for n in nodes],
    }


@app.get("/databases")
async def databases():
    """Retorna detalhes de latência e lag de replicação de cada instância de banco."""
    nodes = await db.ping_all_nodes()
    return {
        "primary": settings.db_primary,
        "replicas": settings.replica_hosts,
        "nodes": [db.node_to_dict(n) for n in nodes],
    }


# ============================================================================
# Algoritmo 1: Ordenação de Eventos (Relógio Lógico de Lamport)
# ============================================================================

class EventCreateRequest(BaseModel):
    """Payload para criação de um evento ordenado por Lamport."""
    event_name: str
    payload: dict[str, Any] = Field(default_factory=dict)


@app.post("/events/ordered")
async def create_ordered_event(req: EventCreateRequest):
    """Gera um evento distribuído, incrementa o relógio de Lamport e grava no Postgres Primary."""
    ts = lamport_clock.tick()
    pool = db._pools.get(settings.db_primary)
    if not pool:
        raise HTTPException(status_code=500, detail="Primary DB not connected")

    async with pool.acquire() as conn:
        row_id = await conn.fetchval(
            """
            INSERT INTO distributed_ordered_events (event_name, lamport_clock, node_id, payload)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            req.event_name,
            ts.clock,
            ts.node_id,
            json.dumps(req.payload),
        )

    # Propaga o relógio de Lamport para os helpers réplica
    for helper in settings.helper_hosts:
        asyncio.create_task(
            async_http_call(
                "POST",
                f"http://{helper}:{settings.helper_port}/lamport/update",
                {"received_clock": ts.clock},
            )
        )

    return {
        "event_id": row_id,
        "event_name": req.event_name,
        "lamport_clock": ts.clock,
        "node_id": ts.node_id,
    }


@app.get("/events/ordered")
async def list_ordered_events(limit: int = 50):
    """Recupera eventos ordenados estritamente pela ordem total de Lamport (clock ASC, node_id ASC)."""
    pool = db._pools.get(settings.db_primary)
    if not pool:
        raise HTTPException(status_code=500, detail="Primary DB not connected")

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, event_name, lamport_clock, node_id, payload, created_at
            FROM distributed_ordered_events
            ORDER BY lamport_clock ASC, node_id ASC
            LIMIT $1
            """,
            limit,
        )

    return [
        {
            "id": r["id"],
            "event_name": r["event_name"],
            "lamport_clock": r["lamport_clock"],
            "node_id": r["node_id"],
            "payload": json.loads(r["payload"]) if isinstance(r["payload"], str) else r["payload"],
            "created_at": r["created_at"].isoformat(),
        }
        for r in rows
    ]


# ============================================================================
# Algoritmo 2: Exclusão Mútua Distribuída (Ricart-Agrawala)
# ============================================================================

class TicketPurchaseRequest(BaseModel):
    """Payload para compra de ingressos."""
    user_id: int
    event_id: int
    quantity: int = Field(gt=0, le=50)


@app.post("/tickets/buy-mutex")
async def buy_ticket_with_mutex(req: TicketPurchaseRequest):
    """Executa a compra de ingressos protegida por Exclusão Mútua Distribuída (Ricart-Agrawala)."""
    # 1. Solicita acesso à seção crítica distribuída
    acquired = await mutex_coordinator.request_access(timeout_seconds=5.0)
    if not acquired:
        raise HTTPException(status_code=504, detail="Timeout acquiring Ricart-Agrawala distributed lock")

    start_critical = time.perf_counter()
    pool = db._pools.get(settings.db_primary)
    if not pool:
        await mutex_coordinator.release_access()
        raise HTTPException(status_code=500, detail="Primary DB not connected")

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                remaining = await conn.fetchval(
                    "SELECT tickets_remaining FROM events WHERE id = $1 FOR UPDATE",
                    req.event_id,
                )
                if remaining is None:
                    raise HTTPException(status_code=404, detail="Event not found")
                if remaining < req.quantity:
                    raise HTTPException(status_code=400, detail="Not enough tickets available")

                await conn.execute(
                    "UPDATE events SET tickets_remaining = tickets_remaining - $1 WHERE id = $2",
                    req.quantity,
                    req.event_id,
                )
                purchase_id = await conn.fetchval(
                    """
                    INSERT INTO ticket_purchase_events (user_id, event_id, quantity, status)
                    VALUES ($1, $2, $3, 'confirmed')
                    RETURNING id
                    """,
                    req.user_id,
                    req.event_id,
                    req.quantity,
                )
        return {
            "status": "confirmed",
            "purchase_id": purchase_id,
            "event_id": req.event_id,
            "quantity": req.quantity,
            "algorithm": "Ricart-Agrawala Mutex",
            "critical_section_ms": round((time.perf_counter() - start_critical) * 1000, 2),
        }
    finally:
        # Libera a seção crítica distribuída e avisa os nós postergados
        await mutex_coordinator.release_access()


# ============================================================================
# Algoritmo 3: Compromisso Atômico (Two-Phase Commit - 2PC)
# ============================================================================

@app.post("/tickets/buy-2pc")
async def buy_ticket_with_2pc(req: TicketPurchaseRequest):
    """Executa a compra de ingressos orquestrada através do protocolo Two-Phase Commit (2PC)."""
    tx_id = f"tx-{uuid.uuid4().hex[:12]}"
    payload = {"user_id": req.user_id, "event_id": req.event_id, "quantity": req.quantity}
    pool = db._pools.get(settings.db_primary)
    if not pool:
        raise HTTPException(status_code=500, detail="Primary DB not connected")

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO two_phase_transactions (tx_id, coordinator_id, state, payload)
            VALUES ($1, $2, 'PREPARING', $3)
            """,
            tx_id,
            settings.node_id,
            json.dumps(payload),
        )

    # Executa o protocolo 2PC com votação dos nós participantes
    success = await two_phase_coordinator.execute_transaction(tx_id, payload, timeout_seconds=4.0)

    final_state = "COMMITTED" if success else "ABORTED"
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE two_phase_transactions SET state = $1, updated_at = NOW() WHERE tx_id = $2",
            final_state,
            tx_id,
        )

    if not success:
        raise HTTPException(status_code=400, detail={"error": "2PC transaction aborted", "tx_id": tx_id})

    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "UPDATE events SET tickets_remaining = tickets_remaining - $1 WHERE id = $2",
                req.quantity,
                req.event_id,
            )
            purchase_id = await conn.fetchval(
                """
                INSERT INTO ticket_purchase_events (user_id, event_id, quantity, status)
                VALUES ($1, $2, $3, 'confirmed-2pc')
                RETURNING id
                """,
                req.user_id,
                req.event_id,
                req.quantity,
            )

    return {
        "status": "committed",
        "tx_id": tx_id,
        "purchase_id": purchase_id,
        "algorithm": "Two-Phase Commit (2PC)",
    }


# ============================================================================
# Algoritmo 4: Detecção de Falhas (Heartbeat)
# ============================================================================

@app.get("/cluster/health")
async def cluster_failure_detector_health():
    """Retorna o status atualizado do detector de falhas por Heartbeat."""
    return {
        "detector": "HeartbeatFailureDetector",
        "interval_seconds": failure_detector.interval_seconds,
        "max_missed_tolerated": failure_detector.max_missed,
        "nodes": failure_detector.get_summary(),
    }
