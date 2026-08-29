import pytest

from simulator.process.tank import Tank


def test_tank_rejects_invalid_capacity():
    with pytest.raises(ValueError):
        Tank(capacity=0)
    with pytest.raises(ValueError):
        Tank(capacity=-10)


def test_tank_rejects_level_outside_capacity():
    with pytest.raises(ValueError):
        Tank(capacity=100, level=150)
    with pytest.raises(ValueError):
        Tank(capacity=100, level=-1)


def test_tick_increases_level_when_inlet_exceeds_outlet():
    tank = Tank(capacity=1000, level=500)
    tank.tick(inlet_flow=50, outlet_flow=0)
    assert tank.level == 550


def test_tick_decreases_level_when_outlet_exceeds_inlet():
    tank = Tank(capacity=1000, level=500)
    tank.tick(inlet_flow=0, outlet_flow=50)
    assert tank.level == 450


def test_tick_clamps_at_capacity():
    tank = Tank(capacity=1000, level=980)
    tank.tick(inlet_flow=100, outlet_flow=0)
    assert tank.level == 1000  # cannot overflow past capacity


def test_tick_clamps_at_zero():
    tank = Tank(capacity=1000, level=20)
    tank.tick(inlet_flow=0, outlet_flow=100)
    assert tank.level == 0  # cannot go negative


def test_tick_rejects_negative_flows():
    tank = Tank(capacity=1000, level=500)
    with pytest.raises(ValueError):
        tank.tick(inlet_flow=-1, outlet_flow=0)
    with pytest.raises(ValueError):
        tank.tick(inlet_flow=0, outlet_flow=-1)


def test_level_percent():
    tank = Tank(capacity=200, level=50)
    assert tank.level_percent == 25.0


def test_is_high_and_is_low():
    tank = Tank(capacity=100, level=95)
    assert tank.is_high(90)
    assert not tank.is_low(10)

    tank.level = 5
    assert tank.is_low(10)
    assert not tank.is_high(90)
