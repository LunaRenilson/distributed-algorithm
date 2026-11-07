"""Testes de integração para a API de algoritmos distribuídos."""

import asyncio
from app.algorithms.lamport import LamportClock
from app.algorithms.ricart_agrawala import NodeState, RicartAgrawalaMutex
from app.algorithms.two_phase_commit import (
    TwoPhaseCoordinator,
    TwoPhaseParticipant,
    TxState,
)
from app.algorithms.heartbeat import HeartbeatFailureDetector


def test_concurrent_lamport_clock_ticks():
    """Valida que múltiplos clientes/threads concorrentes incrementam o relógio de Lamport monotonicamente."""
    clock = LamportClock(node_id="coordinator")
    timestamps = []

    async def worker():
        for _ in range(50):
            ts = clock.tick()
            timestamps.append(ts.clock)
            await asyncio.sleep(0.001)

    async def run():
        tasks = [asyncio.create_task(worker()) for _ in range(4)]
        await asyncio.gather(*tasks)

    asyncio.run(run())

    assert len(timestamps) == 200
    # O valor final deve ser exatamente 200
    assert clock.value == 200
    # Todos os timestamps devem ser estritamente positivos e únicos dentro da ordem gerada
    assert min(timestamps) >= 1
    assert max(timestamps) == 200


def test_distributed_mutex_multi_node_mutual_exclusion():
    """Simula múltiplos nós concorrentes disputando a seção crítica via Ricart-Agrawala."""
    clock_a = LamportClock("node-a")
    clock_b = LamportClock("node-b")

    shared_resource_counter = 0
    in_critical_section = False

    async def send_req_a(peer: str, ts):
        return await mutex_b.receive_request("node-a", ts)

    async def send_reply_a(peer: str):
        await mutex_b.receive_reply("node-a")
        return True

    async def send_req_b(peer: str, ts):
        return await mutex_a.receive_request("node-b", ts)

    async def send_reply_b(peer: str):
        await mutex_a.receive_reply("node-b")
        return True

    mutex_a = RicartAgrawalaMutex("node-a", peers=["node-b"], clock=clock_a, send_request_fn=send_req_a, send_reply_fn=send_reply_a)
    mutex_b = RicartAgrawalaMutex("node-b", peers=["node-a"], clock=clock_b, send_request_fn=send_req_b, send_reply_fn=send_reply_b)

    async def access_resource(mutex: RicartAgrawalaMutex):
        nonlocal shared_resource_counter, in_critical_section
        ok = await mutex.request_access(timeout_seconds=2.0)
        assert ok is True
        # Início da seção crítica
        assert in_critical_section is False
        in_critical_section = True
        shared_resource_counter += 1
        await asyncio.sleep(0.02)
        in_critical_section = False
        # Fim da seção crítica
        await mutex.release_access()

    async def run():
        # Dispara ambos ao mesmo tempo para competir pela seção crítica
        t1 = asyncio.create_task(access_resource(mutex_a))
        t2 = asyncio.create_task(access_resource(mutex_b))
        await asyncio.gather(t1, t2)

    asyncio.run(run())
    assert shared_resource_counter == 2
    assert mutex_a.state == NodeState.RELEASED
    assert mutex_b.state == NodeState.RELEASED


def test_tpc_all_participants_consistency():
    """Testa transação distribuída com 3 participantes verificando consistência atômica."""
    p1 = TwoPhaseParticipant("p1")
    p2 = TwoPhaseParticipant("p2")
    p3 = TwoPhaseParticipant("p3")

    participants_map = {"p1": p1, "p2": p2, "p3": p3}

    async def prepare_call(p: str, tx_id: str, payload: dict) -> bool:
        return await participants_map[p].prepare(tx_id, payload)

    async def commit_call(p: str, tx_id: str) -> bool:
        return await participants_map[p].commit(tx_id)

    async def abort_call(p: str, tx_id: str) -> bool:
        return await participants_map[p].abort(tx_id)

    coord = TwoPhaseCoordinator(
        coordinator_id="coord",
        participants=["p1", "p2", "p3"],
        prepare_call=prepare_call,
        commit_call=commit_call,
        abort_call=abort_call,
    )

    async def run():
        # 1. Transação bem-sucedida
        ok = await coord.execute_transaction("tx-100", {"quantity": 5})
        assert ok is True
        for p in participants_map.values():
            assert p.transactions["tx-100"].state == TxState.COMMITTED

        # 2. Transação onde um participante falha (ex: p2 rejeita por quantidade excessiva)
        async def prepare_call_reject(p: str, tx_id: str, payload: dict) -> bool:
            if p == "p2":
                return False
            return await participants_map[p].prepare(tx_id, payload)

        coord_reject = TwoPhaseCoordinator(
            coordinator_id="coord",
            participants=["p1", "p2", "p3"],
            prepare_call=prepare_call_reject,
            commit_call=commit_call,
            abort_call=abort_call,
        )

        ok_reject = await coord_reject.execute_transaction("tx-101", {"quantity": 999})
        assert ok_reject is False
        for p in participants_map.values():
            assert p.transactions["tx-101"].state == TxState.ABORTED

    asyncio.run(run())
