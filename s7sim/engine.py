"""Threaded S7 runtime. Qt never owns or copies the protocol memory buffers."""

from __future__ import annotations

import logging
import math
import random
import select
import socket
import struct
import threading
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import asdict, dataclass

from snap7.server import (
    CPUState, EVC_CLIENT_EXCEPTION, EVC_CLIENT_NO_ROOM, EVC_DATA_READ,
    EVC_DATA_WRITE, EVC_SERVER_STARTED, EVC_SERVER_STOPPED, Server, ServerState,
)
from snap7.type import SrvArea
from snap7.datatypes import S7DataTypes, S7WordLen
from snap7.s7protocol import S7Function, S7PDUType

from .codec import INT_LIMITS, make_layout, read_value, write_value
from .models import PLC, Project, Simulation

log = logging.getLogger(__name__)


@dataclass
class Connection:
    id: str
    ip: str
    port: int
    connected_at: float
    disconnected_at: float | None = None
    reads: int = 0
    writes: int = 0
    bytes_read: int = 0
    bytes_written: int = 0


class _InterruptibleSocket:
    """Keep snap7's frame deadlines while making idle reads cancellable.

    Closing or shutting down a timed socket from another thread does not
    reliably wake its pending read on every platform. Poll readiness briefly,
    then let the original socket perform each read without changing framing.
    """

    def __init__(self, sock, stopping):
        self._socket = sock
        self._stopping = stopping

    def __getattr__(self, name):
        return getattr(self._socket, name)

    def recv(self, size, flags=0):
        timeout = self._socket.gettimeout()
        if timeout == 0:
            return self._socket.recv(size, flags)
        deadline = time.monotonic() + timeout if timeout is not None else None
        while not self._stopping.is_set():
            remaining = deadline - time.monotonic() if deadline is not None else 0.1
            if remaining <= 0:
                raise TimeoutError('Receive deadline exceeded')
            ready, _, _ = select.select([self._socket], [], [], min(0.1, remaining))
            if ready:
                return self._socket.recv(size, flags)
        raise ConnectionAbortedError('S7 service stopped')


class ObservedServer(Server):
    """Small adapter to pinned snap7 3.2.1 for peer ports and socket cleanup.

    SrvEvent only exposes the peer IP; the client handler supplies the port.
    Cancellable reads and socket shutdown keep stop/restart responsive.
    """

    def __init__(self, owner: PLCRuntime):
        super().__init__(log=False, max_clients=owner.config.max_clients)
        self.owner = owner
        self.local = threading.local()
        self.sockets: dict[tuple, socket.socket] = {}
        self.socket_lock = threading.Lock()
        self.stopping = threading.Event()

    def start(self, tcp_port: int = 102) -> int:
        # Do not use the upstream SO_REUSEPORT: a simulator must have exclusive
        # ownership of its endpoint, including overlapping wildcard binds.
        if self.running:
            raise RuntimeError("服务已经运行")
        self.port = tcp_port
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            listener.bind((self.host, self.port))
            listener.listen(self.max_clients)
        except Exception:
            listener.close()
            raise
        self.server_socket = listener
        self.stopping.clear()
        self.running = True
        self.state = ServerState.RUNNING
        self.cpu_state = CPUState.RUN
        self.server_thread = threading.Thread(target=self._server_loop, daemon=True)
        self.server_thread.start()
        self._emit_event(EVC_SERVER_STARTED)
        return 0

    def _handle_client(self, client_socket, address):
        self.local.address = address
        with self.socket_lock:
            self.sockets[address] = client_socket
        self.owner.connected(address)
        try:
            if not self.running:
                client_socket.close()
            super()._handle_client(_InterruptibleSocket(client_socket, self.stopping), address)
        finally:
            with self.socket_lock:
                self.sockets.pop(address, None)
            self.owner.disconnected(address)

    def _parse_address_specification(self, raw):
        address = super()._parse_address_specification(raw)
        if address:
            address["bit_address"] = int.from_bytes(raw[9:12], "big")
        return address

    def _parse_request_parameters(self, raw):
        if len(raw) >= 2 and raw[0] == S7Function.WRITE_AREA:
            count = raw[1]
            specs = [self._parse_address_specification(raw[i:i + 12]) for i in range(2, len(raw), 12)]
            return {"function_code": raw[0], "item_count": count, "address_specs": specs}
        return super()._parse_request_parameters(raw)

    def _parse_request(self, raw):
        request = super()._parse_request(raw)
        request["raw_data"] = raw[10 + request["param_length"]:]
        return request

    def _get_szl_data(self, szl_id, szl_index):
        if szl_id == 0x001C:
            data = bytearray(super()._get_szl_data(szl_id, szl_index))
            config = self.owner.config
            fields = [(6, 24, config.name), (40, 24, config.cpu),
                      (108, 26, "S7 Studio Simulator"), (142, 24, "SIM-" + config.id[:16]),
                      (176, 32, config.cpu)]
            for offset, size, value in fields:
                data[offset:offset + size] = value.encode("ascii", "replace")[:size - 1].ljust(size, b"\0")
            return bytes(data)
        if szl_id == 0x0011:
            # Deliberately identifies itself as a simulator, not Siemens hardware.
            code = ("SIM-" + self.owner.config.model).encode().ljust(20, b"\0")
            return struct.pack(">HHH", 26, 1, 1) + code + bytes([0, 0, 1, 0])
        if szl_id == 0x0131:
            return struct.pack(">HHHH", 480, self.owner.config.max_clients, 0, 0)
        return super()._get_szl_data(szl_id, szl_index)

    @staticmethod
    def _area_response(request, function, count, data):
        return struct.pack(">BBHHHHBB", 0x32, S7PDUType.ACK_DATA, 0, request["sequence"], 2, len(data), 0, 0) + bytes([function, count]) + data

    def _read_item(self, spec):
        key = spec["area"], spec["db_number"]
        if key not in self.memory_areas:
            return 0x0A, b""
        if spec["word_len"] != S7WordLen.BIT:
            size = S7DataTypes.get_size_bytes(S7WordLen(spec["word_len"]), spec["count"])
            return self._read_from_memory_area(*key, spec["start"], size)
        start, count = spec["bit_address"], spec["count"]
        with self.area_locks[key]:
            memory = self.memory_areas[key]
            if count < 1 or start + count > len(memory) * 8:
                return 0x05, b""
            return 0xFF, bytes((memory[(start + i) // 8] >> ((start + i) % 8)) & 1 for i in range(count))

    def _handle_read_area(self, request, client_address):
        params = request["parameters"]
        specs = params.get("address_specs", [params.get("address_spec", {})])
        count = params.get("item_count", 0)
        if not 1 <= count <= 20 or count != len(specs) or not all(specs):
            return self._build_error_response(request, 0x8001)
        data = bytearray()
        for index, spec in enumerate(specs):
            code, payload = self._read_item(spec)
            bit = spec["word_len"] == S7WordLen.BIT
            transport = (0x03 if bit else 0x04) if code == 0xFF else 0
            data.extend(struct.pack(">BBH", code, transport, len(payload) if bit else len(payload) * 8))
            data.extend(payload)
            if index < count - 1 and len(payload) % 2:
                data.append(0)
            if code == 0xFF:
                self._emit_event(EVC_DATA_READ, param1=self._event_area(spec["area"]), param2=spec["db_number"], param3=spec["start"], param4=len(payload), sender=self._event_sender(client_address))
            else:
                self.owner.add_event("ERROR", f"读取 DB{spec['db_number']} 偏移 {spec['start']} 失败 · 0x{code:02X}", f"{client_address[0]}:{client_address[1]}")
        return self._area_response(request, S7Function.READ_AREA, count, data)

    def _write_item(self, spec, payload):
        key = spec["area"], spec["db_number"]
        if key not in self.memory_areas:
            return 0x0A
        bit = spec["word_len"] == S7WordLen.BIT
        expected = S7DataTypes.get_size_bytes(S7WordLen(spec["word_len"]), spec["count"])
        if len(payload) != expected or not payload:
            return 0x07
        with self.area_locks[key]:
            memory = self.memory_areas[key]
            if bit:
                start = spec["bit_address"]
                if start + len(payload) > len(memory) * 8 or any(v not in (0, 1) for v in payload):
                    return 0x05
                for i, value in enumerate(payload):
                    index, offset = divmod(start + i, 8)
                    memory[index] = (memory[index] & ~(1 << offset)) | (value << offset)
            else:
                start = spec["start"]
                if start < 0 or start + len(payload) > len(memory):
                    return 0x05
                memory[start:start + len(payload)] = payload
        return 0xFF

    def _handle_write_area(self, request, client_address):
        params = request["parameters"]
        specs = params.get("address_specs", [])
        count = params.get("item_count", 0)
        if not 1 <= count <= 20 or count != len(specs) or not all(specs):
            return self._build_error_response(request, 0x8001)
        raw = request["raw_data"]
        offset, items = 0, []
        for i, spec in enumerate(specs):
            if offset + 4 > len(raw):
                return self._build_error_response(request, 0x8001)
            _, transport, length = struct.unpack_from(">BBH", raw, offset)
            size = length if transport in {0x03, 0x07, 0x09} else (length + 7) // 8
            offset += 4
            if offset + size > len(raw):
                return self._build_error_response(request, 0x8001)
            items.append(raw[offset:offset + size])
            offset += size
            if i < count - 1 and size % 2:
                offset += 1
        if offset != len(raw):
            return self._build_error_response(request, 0x8001)
        results = bytearray()
        for spec, payload in zip(specs, items):
            code = self._write_item(spec, payload)
            results.append(code)
            if code == 0xFF:
                self._emit_event(EVC_DATA_WRITE, param1=self._event_area(spec["area"]), param2=spec["db_number"], param3=spec["start"], param4=len(payload), sender=self._event_sender(client_address))
            else:
                self.owner.add_event("ERROR", f"写入 DB{spec['db_number']} 偏移 {spec['start']} 失败 · 0x{code:02X}", f"{client_address[0]}:{client_address[1]}")
        return self._area_response(request, S7Function.WRITE_AREA, count, results)

    def stop(self):
        if not self.running and self.server_socket is None:
            return 0
        # Windows may keep a timed recv/accept blocked after shutdown alone.
        # Signal all readers before joining, and never briefly restore RUNNING
        # just to invoke the upstream bookkeeping.
        self.running = False
        self.stopping.set()
        self.state = ServerState.STOPPED
        self.cpu_state = CPUState.STOP

        def shutdown_socket(sock):
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

        listener = self.server_socket
        if listener is not None:
            shutdown_socket(listener)
            listener.close()
        with self.socket_lock:
            clients = list(self.sockets.values())
        for client in clients:
            shutdown_socket(client)
        with self.client_lock:
            threads = list(self.clients)
        # One shared deadline avoids a delay proportional to the client count.
        deadline = time.monotonic() + 1.5
        for thread in [self.server_thread, *threads]:
            if thread and thread is not threading.current_thread() and thread.is_alive():
                thread.join(timeout=max(0, deadline - time.monotonic()))
        self.server_socket = None
        for client in clients:
            client.close()
        with self.client_lock:
            self.clients[:] = [thread for thread in self.clients if thread.is_alive()]
            self.client_count = len(self.clients)
        self._emit_event(EVC_SERVER_STOPPED)
        return 0


class PLCRuntime:
    def __init__(self, config: PLC):
        config.validate()
        self.config = config
        self.lock = threading.RLock()
        self.server: ObservedServer | None = None
        self.memories = {db.id: db.build_memory() for db in config.blocks}
        self.layouts = {db.id: make_layout(db.variables, db.size)[0] for db in config.blocks}
        self.events: deque[dict] = deque(maxlen=2000)
        self.connections: deque[Connection] = deque(maxlen=1000)
        self.active: dict[tuple, Connection] = {}
        self.reads = self.writes = 0
        self.bytes_read = self.bytes_written = 0
        self.started_at: float | None = None
        self.error = ""
        self.last_tick: dict[str, float] = {}
        self.epoch = time.monotonic()

    @property
    def running(self) -> bool:
        return self.server is not None and self.server.running

    def add_event(self, kind: str, message: str, peer: str = "—"):
        with self.lock:
            self.events.append({"time": time.time(), "kind": kind, "message": message, "peer": peer})

    def connected(self, address):
        with self.lock:
            conn = Connection(f"{address[0]}:{address[1]}-{time.time_ns()}", address[0], address[1], time.time())
            self.connections.append(conn)
            self.active[address] = conn
            self.add_event("CONNECT", "客户端已连接", f"{address[0]}:{address[1]}")

    def disconnected(self, address):
        with self.lock:
            conn = self.active.pop(address, None)
            if conn:
                conn.disconnected_at = time.time()
                self.add_event("DISCONNECT", "客户端已断开", f"{address[0]}:{address[1]}")

    def _event(self, event):
        address = getattr(self.server.local, "address", None) if self.server else None
        peer = f"{address[0]}:{address[1]}" if address else "—"
        with self.lock:
            conn = self.active.get(address)
            if event.EvtCode == EVC_DATA_READ:
                self.reads += 1
                self.bytes_read += event.EvtParam4
                if conn:
                    conn.reads += 1
                    conn.bytes_read += event.EvtParam4
                self.add_event("READ", f"DB{event.EvtParam2} · 偏移 {event.EvtParam3} · {event.EvtParam4} B", peer)
            elif event.EvtCode == EVC_DATA_WRITE:
                self.writes += 1
                self.bytes_written += event.EvtParam4
                if conn:
                    conn.writes += 1
                    conn.bytes_written += event.EvtParam4
                self.add_event("WRITE", f"DB{event.EvtParam2} · 偏移 {event.EvtParam3} · {event.EvtParam4} B", peer)
            elif event.EvtCode in {EVC_CLIENT_EXCEPTION, EVC_CLIENT_NO_ROOM}:
                self.add_event("ERROR", "客户端协议异常" if event.EvtCode == EVC_CLIENT_EXCEPTION else "达到最大连接数，已拒绝连接", peer)

    def start(self):
        if self.running:
            return
        if self.server:
            self.stop()
        server = ObservedServer(self)
        self.server = server
        for db in self.config.blocks:
            server.register_area(SrvArea.DB, db.number, self.memories[db.id])
        server.set_events_callback(self._event)
        server.host = self.config.host
        try:
            server.start(self.config.port)
        except Exception as exc:
            self.error = str(exc)
            self.server = None
            self.add_event("ERROR", f"启动失败：{exc}")
            raise
        self.started_at = time.time()
        self.epoch = time.monotonic()
        self.last_tick.clear()
        self.error = ""
        self.add_event("START", f"S7 服务监听 {self.config.host}:{self.config.port}")

    def stop(self):
        server = self.server
        if server is None:
            return
        server.stop()
        self.server = None
        self.snapshot_values()
        self.add_event("STOP", "S7 服务已停止，内存值已保留")

    @contextmanager
    def memory_lock(self, db):
        server = self.server
        if server:
            server.lock_area(SrvArea.DB, db.number)
        try:
            yield self.memories[db.id]
        finally:
            if server:
                server.unlock_area(SrvArea.DB, db.number)

    def read_block(self, db):
        with self.memory_lock(db) as memory:
            result = []
            for layout in self.layouts[db.id]:
                try:
                    result.append((read_value(memory, layout), None))
                except (ValueError, OverflowError, UnicodeError) as exc:
                    result.append((None, f"内存值无效：{exc}"))
            return result, bytes(memory)

    def set_value(self, db, index: int, value):
        var = db.variables[index]
        with self.memory_lock(db) as memory:
            write_value(memory, self.layouts[db.id][index], value, var.length)
            var.value = read_value(memory, self.layouts[db.id][index])
        self.add_event("EDIT", f"DB{db.number}.{var.name} 手动写入")

    def set_simulation(self, db, index: int, simulation: Simulation):
        var = db.variables[index]
        simulation.validate(var.dtype)
        with self.lock:
            var.simulation = simulation
            self.last_tick.pop(var.id, None)
        self.add_event("SIM", f"DB{db.number}.{var.name} → {simulation.mode}")

    def tick(self, now: float):
        if not self.running or self.server.cpu_state != CPUState.RUN:
            return
        for db in self.config.blocks:
            for i, var in enumerate(db.variables):
                with self.lock:
                    sim = var.simulation
                    if sim.mode == "manual" or now - self.last_tick.get(var.id, 0) < sim.interval_ms / 1000:
                        continue
                    self.last_tick[var.id] = now
                try:
                    with self.memory_lock(db) as memory:
                        if not self.running or self.server.cpu_state != CPUState.RUN or var.simulation is not sim:
                            continue
                        if var.dtype == "BOOL":
                            old = read_value(memory, self.layouts[db.id][i])
                            values = old if var.count > 1 else [old]
                            values = [not v if sim.mode == "toggle" else bool(random.getrandbits(1)) for v in values]
                        else:
                            phase = ((now - self.epoch) * 1000 % sim.period_ms) / sim.period_ms
                            fraction = (math.sin(phase * 2 * math.pi) + 1) / 2 if sim.mode == "sine" else phase
                            values = []
                            for _ in range(var.count):
                                if sim.mode == "random":
                                    v = random.randint(math.ceil(sim.minimum), math.floor(sim.maximum)) if var.dtype in INT_LIMITS else (lambda f: sim.minimum * (1 - f) + sim.maximum * f)(random.random())
                                else:
                                    v = sim.minimum * (1 - fraction) + sim.maximum * fraction
                                    if var.dtype in INT_LIMITS:
                                        v = min(math.floor(sim.maximum), max(math.ceil(sim.minimum), round(v)))
                                values.append(v)
                        write_value(memory, self.layouts[db.id][i], values if var.count > 1 else values[0], var.length)
                except Exception as exc:
                    with self.lock:
                        var.simulation = Simulation()
                    self.add_event("ERROR", f"{var.name} 模拟已停止：{exc}")

    def snapshot_values(self):
        for db in self.config.blocks:
            values, _ = self.read_block(db)
            for var, (value, error) in zip(db.variables, values):
                if error is None:
                    var.value = value

    def statistics(self, include_history=True) -> dict:
        with self.lock:
            return {"running": self.running, "connections": len(self.active), "reads": self.reads, "writes": self.writes,
                    "bytes_read": self.bytes_read, "bytes_written": self.bytes_written,
                    "started_at": self.started_at, "error": self.error,
                    "peers": [asdict(c) for c in reversed(self.connections)] if include_history else [], "events": list(reversed(self.events)) if include_history else []}


class Engine:
    def __init__(self, project: Project):
        self.project = project
        self.lock = threading.RLock()
        self.runtimes: dict[str, PLCRuntime] = {plc.id: PLCRuntime(plc) for plc in project.plcs}
        self.closed = threading.Event()
        self.thread = threading.Thread(target=self._loop, name="s7-simulation", daemon=True)
        self.thread.start()

    def _loop(self):
        while not self.closed.wait(0.02):
            with self.lock:
                runtimes = list(self.runtimes.values())
            for runtime in runtimes:
                try:
                    runtime.tick(time.monotonic())
                except Exception:
                    log.exception("Simulation tick failed")

    def runtime(self, plc: PLC) -> PLCRuntime:
        return self.runtimes[plc.id]

    def rebuild(self, plc: PLC):
        with self.lock:
            old = self.runtimes.get(plc.id)
            if old and old.running:
                raise ValueError("请先停止此 PLC，再修改 DB 结构")
            replacement = PLCRuntime(plc)
            if old:
                if old.server:
                    old.stop()
                replacement.events = old.events
                replacement.connections = old.connections
                replacement.reads, replacement.writes = old.reads, old.writes
                replacement.bytes_read, replacement.bytes_written = old.bytes_read, old.bytes_written
            self.runtimes[plc.id] = replacement

    def remove(self, plc: PLC):
        runtime = self.runtimes.get(plc.id)
        if runtime:
            runtime.stop()
            with self.lock:
                self.runtimes.pop(plc.id, None)

    def snapshot(self):
        with self.lock:
            runtimes = list(self.runtimes.values())
        for runtime in runtimes:
            runtime.snapshot_values()

    def close(self):
        self.closed.set()
        self.thread.join(timeout=2)
        for runtime in list(self.runtimes.values()):
            runtime.stop()
