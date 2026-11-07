import asyncio
from app.algorithms.heartbeat import HeartbeatFailureDetector


def test_heartbeat_alive_node():
    async def run():
        async def mock_ping(node: str) -> bool:
            return True

        detector = HeartbeatFailureDetector(
            nodes=["node-1", "node-2"],
            ping_fn=mock_ping,
            max_missed=2,
        )

        alive = await detector.check_node("node-1")
        assert alive is True
        assert detector.is_alive("node-1") is True
        assert detector.status["node-1"].missed_count == 0
    asyncio.run(run())


def test_heartbeat_detects_failure_after_max_missed():
    async def run():
        healthy = True

        async def mock_ping(node: str) -> bool:
            return healthy

        detector = HeartbeatFailureDetector(
            nodes=["node-1"],
            ping_fn=mock_ping,
            max_missed=3,
        )

        await detector.check_node("node-1")
        assert detector.is_alive("node-1") is True

        healthy = False

        await detector.check_node("node-1")
        assert detector.status["node-1"].missed_count == 1
        assert detector.is_alive("node-1") is True

        await detector.check_node("node-1")
        assert detector.status["node-1"].missed_count == 2
        assert detector.is_alive("node-1") is True

        await detector.check_node("node-1")
        assert detector.status["node-1"].missed_count == 3
        assert detector.is_alive("node-1") is False
    asyncio.run(run())
