from simulator.process.sensors import PressureSensor, TemperatureSensor


def test_temperature_rises_toward_ceiling_when_cooling_off():
    sensor = TemperatureSensor(temperature=40.0, heating_ceiling=120.0, step_rate=0.1)
    sensor.tick(cooling_active=False)
    assert sensor.temperature > 40.0
    assert sensor.temperature < 120.0  # gradual, not instant


def test_temperature_falls_toward_floor_when_cooling_on():
    sensor = TemperatureSensor(temperature=100.0, cooling_floor=20.0, step_rate=0.1)
    sensor.tick(cooling_active=True)
    assert sensor.temperature < 100.0
    assert sensor.temperature > 20.0  # gradual, not instant


def test_temperature_converges_over_many_ticks():
    sensor = TemperatureSensor(temperature=40.0, heating_ceiling=120.0, step_rate=0.2)
    for _ in range(200):
        sensor.tick(cooling_active=False)
    assert abs(sensor.temperature - 120.0) < 0.01


def test_pressure_rises_with_tank_level():
    low_level = PressureSensor(pressure=1.0, step_rate=1.0)
    low_level.tick(tank_level_percent=0.0, temperature=25.0)

    high_level = PressureSensor(pressure=1.0, step_rate=1.0)
    high_level.tick(tank_level_percent=100.0, temperature=25.0)

    assert high_level.pressure > low_level.pressure


def test_pressure_rises_with_temperature():
    cool = PressureSensor(pressure=1.0, step_rate=1.0)
    cool.tick(tank_level_percent=50.0, temperature=25.0)

    hot = PressureSensor(pressure=1.0, step_rate=1.0)
    hot.tick(tank_level_percent=50.0, temperature=150.0)

    assert hot.pressure > cool.pressure
