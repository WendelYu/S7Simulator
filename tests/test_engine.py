import socket
import struct
import time

import pytest
import snap7
from snap7.type import Area, WordLen
from snap7.datatypes import S7Area, S7WordLen

from s7sim.engine import Engine, PLCRuntime
from s7sim.models import DataBlock, PLC, Project, Simulation, Variable


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_until(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    assert predicate(), "Timed out waiting for runtime state"


@pytest.fixture
def runtime():
    db = DataBlock(variables=[Variable(name="value", dtype="REAL", value=24.5),
                              Variable(name="array", dtype="INT", count=3, value=[1, 2, 3])])
    runtime = PLCRuntime(PLC(port=free_port(), blocks=[db]))
    runtime.start()
    yield runtime
    runtime.stop()


def connect(runtime):
    client = snap7.Client()
    client.connect("127.0.0.1", 0, 1, tcp_port=runtime.config.port)
    return client


def disconnect(client):
    client.disconnect()
    client.destroy()


def test_real_s7_reads_writes_and_connection_monitor(runtime):
    clients = [connect(runtime) for _ in range(3)]
    try:
        wait_until(lambda: runtime.statistics()["connections"] == 3)
        assert len({p["port"] for p in runtime.statistics()["peers"]}) == 3
        assert struct.unpack(">f", clients[0].db_read(1, 0, 4))[0] == 24.5
        clients[0].db_write(1, 0, bytearray(struct.pack(">f", 72.25)))
        db = runtime.config.blocks[0]
        assert runtime.read_block(db)[0][0][0] == 72.25
        runtime.set_value(db, 1, [100, -200, 300])
        assert struct.unpack(">hhh", clients[1].db_read(1, 4, 6)) == (100, -200, 300)
        stats = runtime.statistics()
        assert stats["reads"] == 2
        assert stats["writes"] == 1
        assert stats["bytes_read"] == 10
        assert stats["bytes_written"] == 4
        assert sum(p["writes"] for p in stats["peers"]) == 1
    finally:
        for client in clients:
            disconnect(client)
    wait_until(lambda: runtime.statistics()["connections"] == 0)
    assert all(p["disconnected_at"] for p in runtime.statistics()["peers"])


def test_stop_closes_idle_clients_and_releases_port(runtime):
    clients = [connect(runtime) for _ in range(4)]
    wait_until(lambda: runtime.statistics()["connections"] == 4)
    start = time.monotonic()
    runtime.stop()
    assert time.monotonic() - start < 2
    assert runtime.statistics()["connections"] == 0
    assert not runtime.running
    runtime.start()
    new_client = connect(runtime)
    assert len(new_client.db_read(1, 0, 4)) == 4
    disconnect(new_client)
    for client in clients:
        disconnect(client)


def test_port_collision_is_not_silently_shared(runtime):
    other = PLCRuntime(PLC(port=runtime.config.port))
    with pytest.raises(OSError):
        other.start()
    assert not other.running
    assert other.statistics()["error"]
    assert runtime.running


def test_bit_access_preserves_adjacent_bits_and_crosses_byte_boundary(runtime):
    client = connect(runtime)
    try:
        client.db_write(1, 100, bytearray([0b10100101, 0b00000011]))
        assert client.read_area(Area.DB, 1, 100 * 8 + 2, 1, WordLen.Bit) == b"\x01"
        client.write_area(Area.DB, 1, 100 * 8 + 1, bytearray([1]), WordLen.Bit)
        assert client.db_read(1, 100, 2) == b"\xa7\x03"
        values = bytearray([1, 0, 1, 1, 0, 0, 1, 0, 1, 1])
        client.write_area(Area.DB, 1, 100 * 8 + 3, values, WordLen.Bit)
        assert client.read_area(Area.DB, 1, 100 * 8 + 3, 10, WordLen.Bit) == values
        assert client.db_read(1, 100, 1)[0] & 0b111 == 0b111
    finally:
        disconnect(client)


def test_out_of_bounds_write_fails_without_partial_mutation(runtime):
    client = connect(runtime)
    try:
        client.db_write(1, 510, bytearray([42, 43]))
        with pytest.raises(Exception):
            client.db_write(1, 511, bytearray([99, 100]))
        assert client.db_read(1, 510, 2) == b"\x2a\x2b"
        with pytest.raises(Exception):
            client.db_read(999, 0, 4)
        assert any(event["kind"] == "ERROR" for event in runtime.statistics()["events"])
    finally:
        disconnect(client)


def test_model_identity_explicitly_identifies_simulator(runtime):
    client = connect(runtime)
    try:
        info = client.get_cpu_info()
        assert bytes(info.ModuleTypeName).rstrip(b"\0") == b"CPU 1511-1 PN"
        assert bytes(info.SerialNumber).startswith(b"SIM-")
        assert bytes(client.get_order_code().OrderCode).startswith(b"SIM-S7-1500")
        assert client.get_cp_info().MaxConnections == runtime.config.max_clients
    finally:
        disconnect(client)


def test_wire_multi_write_and_mixed_bit_byte_multi_read(runtime):
    client = connect(runtime)
    try:
        first = client.protocol.build_write_request(S7Area.DB, 1, 100, S7WordLen.BYTE, b"\x02")
        second = client.protocol.build_write_request(S7Area.DB, 1, 0, S7WordLen.BYTE, struct.pack(">f", 88.5))
        parameters = b"\x05\x02" + first[12:24] + second[12:24]
        payload = first[24:] + b"\0" + second[24:]
        header = bytearray(second[:10])
        struct.pack_into(">HH", header, 6, len(parameters), len(payload))
        connection = client._get_connection()
        connection.send_data(bytes(header) + parameters + payload)
        response = connection.receive_data()
        assert response[12:14] == b"\x05\x02"
        assert response[14:] == b"\xff\xff"
        assert client.db_read(1, 100, 1) == b"\x02"
        assert struct.unpack(">f", client.db_read(1, 0, 4))[0] == 88.5

        first = client.protocol.build_read_request(S7Area.DB, 1, 801, S7WordLen.BIT, 1)
        second = client.protocol.build_read_request(S7Area.DB, 1, 0, S7WordLen.BYTE, 4)
        parameters = b"\x04\x02" + first[12:24] + second[12:24]
        header = bytearray(second[:10])
        struct.pack_into(">HH", header, 6, len(parameters), 0)
        connection.send_data(bytes(header) + parameters)
        response = connection.receive_data()
        assert response[12:14] == b"\x04\x02"
        assert response[14:] == b"\xff\x03\x00\x01\x01\0\xff\x04\x00\x20" + struct.pack(">f", 88.5)
    finally:
        disconnect(client)


def test_multiple_plcs_have_independent_memory(runtime):
    other = PLCRuntime(PLC(port=free_port(), blocks=[DataBlock(variables=[Variable(value=11.0)])]))
    other.start()
    client = connect(other)
    try:
        assert struct.unpack(">f", client.db_read(1, 0, 4))[0] == 11.0
        runtime.set_value(runtime.config.blocks[0], 0, 99.0)
        assert struct.unpack(">f", client.db_read(1, 0, 4))[0] == 11.0
    finally:
        disconnect(client)
        other.stop()


def test_random_simulation_cpu_stop_and_rule_change():
    var = Variable(dtype="INT", value=0, simulation=Simulation("random", 10, 20, 50))
    db = DataBlock(variables=[var])
    plc = PLC(port=free_port(), blocks=[db])
    engine = Engine(Project(plcs=[plc]))
    runtime = engine.runtime(plc)
    try:
        runtime.start()
        wait_until(lambda: 10 <= runtime.read_block(db)[0][0][0] <= 20)
        runtime.server.set_cpu_status(4)
        runtime.set_value(db, 0, 100)
        time.sleep(0.15)
        assert runtime.read_block(db)[0][0][0] == 100
        runtime.server.set_cpu_status(8)
        wait_until(lambda: 10 <= runtime.read_block(db)[0][0][0] <= 20)
        runtime.set_simulation(db, 0, Simulation())
        runtime.set_value(db, 0, 200)
        time.sleep(0.15)
        assert runtime.read_block(db)[0][0][0] == 200
        engine.snapshot()
        assert var.value == 200
        with pytest.raises(ValueError):
            engine.rebuild(plc)
    finally:
        engine.close()


def test_invalid_client_date_memory_does_not_crash_snapshot():
    var = Variable(dtype="DATE_AND_TIME", value="2026-01-01T00:00:00")
    db = DataBlock(variables=[var])
    runtime = PLCRuntime(PLC(blocks=[db]))
    runtime.memories[db.id][1] = 0xFF
    assert runtime.read_block(db)[0][0][1]
    runtime.snapshot_values()
    assert var.value == "2026-01-01T00:00:00"


def test_nonfinite_client_float_does_not_poison_saved_project(tmp_path):
    var = Variable(dtype="REAL", value=12.0)
    db = DataBlock(variables=[var])
    plc = PLC(blocks=[db])
    runtime = PLCRuntime(plc)
    runtime.memories[db.id][:4] = struct.pack(">f", float("nan"))
    assert runtime.read_block(db)[0][0][1]
    runtime.snapshot_values()
    assert var.value == 12.0
    Project(plcs=[plc]).save(tmp_path / "project.json")


def test_max_connections_enforced():
    runtime = PLCRuntime(PLC(port=free_port(), max_clients=1))
    runtime.start()
    first = socket.create_connection(("127.0.0.1", runtime.config.port))
    second = None
    try:
        wait_until(lambda: runtime.statistics()["connections"] == 1)
        second = socket.create_connection(("127.0.0.1", runtime.config.port))
        second.settimeout(1)
        assert second.recv(1) == b""
        assert runtime.statistics()["connections"] == 1
        assert any("最大连接数" in event["message"] for event in runtime.statistics()["events"])
    finally:
        first.close()
        if second:
            second.close()
        runtime.stop()


def test_manual_address_visible_to_s7_client():
    db = DataBlock(variables=[Variable(name="manual", dtype="REAL", value=42.5, offset=100, storage_size=12)])
    runtime = PLCRuntime(PLC(port=free_port(), blocks=[db]))
    runtime.start()
    client = connect(runtime)
    try:
        assert struct.unpack(">f", client.db_read(1, 100, 4))[0] == 42.5
        client.db_write(1, 100, bytearray(struct.pack(">f", 99.5)))
        assert runtime.read_block(db)[0][0][0] == 99.5
    finally:
        disconnect(client)
        runtime.stop()


def test_port_suggestion_skips_busy_and_project_ports():
    from s7sim.models import available_port
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        occupied = listener.getsockname()[1]
        port = available_port([PLC(port=1102), PLC(port=1103)])
        assert port not in {1102, 1103, occupied}


def test_all_simulation_modes_and_numeric_types(monkeypatch):
    from s7sim.codec import NUMERIC, default_value
    variables = []
    for dtype in sorted(NUMERIC):
        for mode in ('random', 'sine', 'ramp'):
            variables.append(Variable(name=f'{dtype}_{mode}', dtype=dtype, value=default_value(dtype, 2), count=2, simulation=Simulation(mode, 0, 10, 50, 1000)))
    variables += [Variable(name='toggle', dtype='BOOL', value=[False, True], count=2, simulation=Simulation('toggle', interval_ms=50)),
                  Variable(name='boolean_random', dtype='BOOL', value=False, simulation=Simulation('random', interval_ms=50))]
    db = DataBlock(size=4096, variables=variables)
    runtime = PLCRuntime(PLC(port=free_port(), blocks=[db]))
    monkeypatch.setattr('s7sim.engine.random.getrandbits', lambda _: 1)
    runtime.start()
    try:
        runtime.tick(runtime.epoch + .25)
        values, _ = runtime.read_block(db)
        for var, (value, error) in zip(variables[:-2], values[:-2]):
            assert not error
            assert all(0 <= v <= 10 for v in value)
            if var.simulation.mode == 'sine':
                assert value == [10, 10]
        assert values[-2][0] == [True, False]
        assert values[-1][0] is True
        runtime.tick(runtime.epoch + .75)
        values, _ = runtime.read_block(db)
        assert values[-2][0] == [False, True]
        for var, (value, error) in zip(variables[:-2], values[:-2]):
            if var.simulation.mode == 'sine':
                assert value == [0, 0]
        runtime.server.set_cpu_status(4)
        frozen = bytes(runtime.memories[db.id])
        runtime.tick(runtime.epoch + 1.0)
        assert bytes(runtime.memories[db.id]) == frozen
        assert not any(event['kind'] == 'ERROR' for event in runtime.statistics()['events'])
    finally:
        runtime.stop()


def test_degenerate_wave_timing_rejected():
    for mode in ('sine', 'ramp'):
        with pytest.raises(ValueError, match='更新间隔'):
            Simulation(mode, 0, 10, 1000, 1000).validate('REAL')
