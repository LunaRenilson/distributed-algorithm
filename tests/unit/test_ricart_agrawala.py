import asyncio
from app.algorithms.lamport import LamportClock, LamportTimestamp
from app.algorithms.ricart_agrawala import NodeState, RicartAgrawalaMutex


def test_mutex_single_node_immediate_access():
    async def run():
        mutex = RicartAgrawalaMutex(node_id="node-1", peers=[])
        assert mutex.state == NodeState.RELEASED
        ok = await mutex.request_access()
        assert ok is True
        assert mutex.state == NodeState.HELD
        await mutex.release_access()
        assert mutex.state == NodeState.RELEASED
    asyncio.run(run())


def test_mutex_request_granted_when_peer_released():
    async def run():
        peer_replies = []

        async def mock_send_request(peer: str, ts: LamportTimestamp) -> bool:
            peer_replies.append((peer, ts))
            return True

        mutex = RicartAgrawalaMutex(
            node_id="node-1",
            peers=["node-2", "node-3"],
            send_request_fn=mock_send_request,
        )

        ok = await mutex.request_access(timeout_seconds=1.0)
        assert ok is True
        assert mutex.state == NodeState.HELD
        assert len(peer_replies) == 2
    asyncio.run(run())


def test_mutex_defer_request_when_held():
    async def run():
        mutex = RicartAgrawalaMutex(node_id="node-1", peers=["node-2"])
        mutex.state = NodeState.HELD

        req_ts = LamportTimestamp(clock=10, node_id="node-2")
        granted = await mutex.receive_request("node-2", req_ts)

        assert granted is False
        assert "node-2" in mutex.deferred_replies

        replied = await mutex.release_access()
        assert "node-2" in replied
        assert len(mutex.deferred_replies) == 0
    asyncio.run(run())


def test_mutex_priority_ordering_when_both_wanted():
    async def run():
        clock1 = LamportClock("node-1", initial_clock=4)
        mutex1 = RicartAgrawalaMutex(node_id="node-1", peers=["node-2"], clock=clock1)
        
        mutex1.state = NodeState.WANTED
        mutex1.request_timestamp = LamportTimestamp(clock=5, node_id="node-1")

        # Node-2 pede permissão com timestamp MAIOR (clock=8, prioridade MENOR)
        req_ts2 = LamportTimestamp(clock=8, node_id="node-2")
        grant_to_2 = await mutex1.receive_request("node-2", req_ts2)
        assert grant_to_2 is False
        assert "node-2" in mutex1.deferred_replies

        # Node-3 pede permissão com timestamp MENOR (clock=2, prioridade MAIOR)
        req_ts3 = LamportTimestamp(clock=2, node_id="node-3")
        grant_to_3 = await mutex1.receive_request("node-3", req_ts3)
        assert grant_to_3 is True
        assert "node-3" not in mutex1.deferred_replies
    asyncio.run(run())
