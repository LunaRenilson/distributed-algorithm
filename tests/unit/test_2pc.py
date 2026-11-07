import asyncio
from app.algorithms.two_phase_commit import (
    TwoPhaseCoordinator,
    TwoPhaseParticipant,
    TxState,
)


def test_tpc_successful_commit():
    async def run():
        p1 = TwoPhaseParticipant("p1")
        p2 = TwoPhaseParticipant("p2")

        async def mock_prepare(p: str, tx_id: str, payload: dict) -> bool:
            if p == "p1":
                return await p1.prepare(tx_id, payload)
            return await p2.prepare(tx_id, payload)

        async def mock_commit(p: str, tx_id: str) -> bool:
            if p == "p1":
                return await p1.commit(tx_id)
            return await p2.commit(tx_id)

        async def mock_abort(p: str, tx_id: str) -> bool:
            if p == "p1":
                return await p1.abort(tx_id)
            return await p2.abort(tx_id)

        coord = TwoPhaseCoordinator(
            coordinator_id="coord",
            participants=["p1", "p2"],
            prepare_call=mock_prepare,
            commit_call=mock_commit,
            abort_call=mock_abort,
        )

        success = await coord.execute_transaction("tx-1", {"event_id": 1, "tickets": 2})
        assert success is True
        assert coord.transactions["tx-1"].state == TxState.COMMITTED
        assert p1.transactions["tx-1"].state == TxState.COMMITTED
        assert p2.transactions["tx-1"].state == TxState.COMMITTED
    asyncio.run(run())


def test_tpc_aborts_when_participant_rejects():
    async def run():
        p1 = TwoPhaseParticipant("p1")
        p2 = TwoPhaseParticipant("p2")

        def p2_validator(payload: dict) -> bool:
            return False

        async def mock_prepare(p: str, tx_id: str, payload: dict) -> bool:
            if p == "p1":
                return await p1.prepare(tx_id, payload)
            return await p2.prepare(tx_id, payload, validator=p2_validator)

        async def mock_commit(p: str, tx_id: str) -> bool:
            target = p1 if p == "p1" else p2
            return await target.commit(tx_id)

        async def mock_abort(p: str, tx_id: str) -> bool:
            target = p1 if p == "p1" else p2
            return await target.abort(tx_id)

        coord = TwoPhaseCoordinator(
            coordinator_id="coord",
            participants=["p1", "p2"],
            prepare_call=mock_prepare,
            commit_call=mock_commit,
            abort_call=mock_abort,
        )

        success = await coord.execute_transaction("tx-2", {"event_id": 1, "tickets": 100})
        assert success is False
        assert coord.transactions["tx-2"].state == TxState.ABORTED
        assert p1.transactions["tx-2"].state == TxState.ABORTED
        assert p2.transactions["tx-2"].state == TxState.ABORTED
    asyncio.run(run())
