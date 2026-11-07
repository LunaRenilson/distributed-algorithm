import pytest
from app.algorithms.lamport import LamportClock, LamportTimestamp


def test_lamport_clock_initialization():
    clock = LamportClock("node-1", initial_clock=0)
    assert clock.value == 0
    assert clock.node_id == "node-1"


def test_lamport_clock_tick_increments():
    clock = LamportClock("node-1", initial_clock=5)
    ts = clock.tick()
    assert ts.clock == 6
    assert ts.node_id == "node-1"
    assert clock.value == 6


def test_lamport_clock_update_causality():
    # Cenário: nó 1 está no clock 2 e recebe mensagem com clock 10 do nó 2
    c1 = LamportClock("node-1", initial_clock=2)
    ts = c1.update(received_clock=10)
    # Deve atualizar para max(2, 10) + 1 = 11
    assert ts.clock == 11
    assert ts.node_id == "node-1"
    assert c1.value == 11

    # Cenário: nó 1 está no clock 15 e recebe mensagem com clock 4
    ts2 = c1.update(received_clock=4)
    # max(11, 4) + 1 = 12
    assert ts2.clock == 12


def test_lamport_total_order_tie_breaking():
    # Mesmos clocks, desempate por node_id lexicográfico
    ts_a = LamportTimestamp(clock=5, node_id="node-1")
    ts_b = LamportTimestamp(clock=5, node_id="node-2")
    ts_c = LamportTimestamp(clock=6, node_id="node-0")

    assert ts_a < ts_b
    assert ts_a < ts_c
    assert ts_b < ts_c
