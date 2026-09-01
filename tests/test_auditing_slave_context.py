from pymodbus.datastore import ModbusSequentialDataBlock

from simulator.modbus.server import AuditingSlaveContext


def _make_context(on_write=None) -> AuditingSlaveContext:
    return AuditingSlaveContext(
        hr=ModbusSequentialDataBlock(0, [0] * 4),
        co=ModbusSequentialDataBlock(0, [False] * 2),
        zero_mode=True,
        on_write=on_write,
    )


def test_write_single_register_fc6_triggers_on_write():
    calls = []
    context = _make_context(on_write=lambda fc, addr, values: calls.append((fc, addr, values)))

    context.setValues(6, 0, [4200])

    assert calls == [(6, 0, [4200])]
    assert context.getValues(3, 0, 1) == [4200]  # the write still actually applies


def test_write_multiple_registers_fc16_triggers_on_write():
    calls = []
    context = _make_context(on_write=lambda fc, addr, values: calls.append((fc, addr, values)))

    context.setValues(16, 0, [1, 2])

    assert calls == [(16, 0, [1, 2])]


def test_internal_tick_update_fc3_does_not_trigger_on_write():
    calls = []
    context = _make_context(on_write=lambda fc, addr, values: calls.append((fc, addr, values)))

    # This mirrors exactly what _updater_loop does every tick.
    context.setValues(3, 0, [9000])

    assert calls == []
    assert context.getValues(3, 0, 1) == [9000]  # value still applies, just silently


def test_internal_coil_update_fc1_does_not_trigger_on_write():
    calls = []
    context = _make_context(on_write=lambda fc, addr, values: calls.append((fc, addr, values)))

    context.setValues(1, 0, [True])

    assert calls == []


def test_no_on_write_callback_is_safe():
    context = _make_context(on_write=None)
    # Should not raise even though no callback was supplied.
    context.setValues(6, 0, [1])
    assert context.getValues(3, 0, 1) == [1]
