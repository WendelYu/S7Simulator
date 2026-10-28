from __future__ import annotations

import copy
import json
import math
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .codec import INT_LIMITS, NUMERIC, default_value, make_layout, write_value

PROFILES = {
    "S7-300": {"cpu": "CPU 315-2 PN/DP", "rack": 0, "slot": 2},
    "S7-400": {"cpu": "CPU 414-3 PN/DP", "rack": 0, "slot": 3},
    "S7-1200": {"cpu": "CPU 1214C DC/DC/DC", "rack": 0, "slot": 1},
    "S7-1500": {"cpu": "CPU 1511-1 PN", "rack": 0, "slot": 1},
}


def uid() -> str:
    return uuid.uuid4().hex


@dataclass
class Simulation:
    mode: str = "manual"
    minimum: float = 0
    maximum: float = 100
    interval_ms: int = 1000
    period_ms: int = 10000

    def validate(self, dtype: str) -> None:
        if self.mode not in {"manual", "random", "sine", "ramp", "toggle"}:
            raise ValueError("未知模拟模式")
        if not 50 <= self.interval_ms <= 3_600_000:
            raise ValueError("更新间隔必须在 50–3600000 ms 之间")
        if not 100 <= self.period_ms <= 86_400_000:
            raise ValueError("周期必须在 100–86400000 ms 之间")
        if self.mode in {"sine", "ramp"} and self.interval_ms >= self.period_ms:
            raise ValueError("波形更新间隔必须小于周期，否则每次采样可能停在相同相位")
        if self.mode == "manual":
            return
        if dtype == "BOOL":
            if self.mode not in {"random", "toggle"}:
                raise ValueError("BOOL 支持随机或翻转模式")
            return
        if dtype not in NUMERIC or self.mode == "toggle":
            raise ValueError("该数据类型不支持此模拟模式")
        if not all(math.isfinite(v) for v in (self.minimum, self.maximum)) or self.minimum > self.maximum:
            raise ValueError("上下限必须是有限数值，且下限不能大于上限")
        if dtype in INT_LIMITS:
            lo, hi = INT_LIMITS[dtype]
            if not lo <= self.minimum <= self.maximum <= hi:
                raise ValueError(f"{dtype} 模拟范围必须在 {lo}–{hi} 内")
            if math.ceil(self.minimum) > math.floor(self.maximum):
                raise ValueError("模拟范围内必须至少包含一个整数")
        if dtype == "REAL" and max(abs(self.minimum), abs(self.maximum)) > 3.4028234e38:
            raise ValueError("模拟范围超出 REAL 可表示范围")


@dataclass
class Variable:
    offset: int | None = None
    bit_offset: int = 0
    storage_size: int | None = None
    name: str = "Variable"
    dtype: str = "REAL"
    count: int = 1
    length: int = 32
    value: object = 0.0
    comment: str = ""
    simulation: Simulation = field(default_factory=Simulation)
    id: str = field(default_factory=uid)


@dataclass
class DataBlock:
    number: int = 1
    name: str = "Data_Block"
    size: int = 512
    variables: list[Variable] = field(default_factory=list)
    id: str = field(default_factory=uid)

    def build_memory(self) -> bytearray:
        if not 1 <= self.number <= 65535:
            raise ValueError("DB 编号必须在 1–65535 之间")
        if not 1 <= self.size <= 65536:
            raise ValueError("DB 容量必须在 1–65536 字节之间")
        layouts, _ = make_layout(self.variables, self.size)
        memory = bytearray(self.size)
        for var, layout in zip(self.variables, layouts):
            var.simulation.validate(var.dtype)
            write_value(memory, layout, var.value, var.length)
        return memory


@dataclass
class PLC:
    name: str = "Production Line 01"
    model: str = "S7-1500"
    host: str = "127.0.0.1"
    port: int = 1102
    rack: int = 0
    slot: int = 1
    max_clients: int = 32
    blocks: list[DataBlock] = field(default_factory=list)
    id: str = field(default_factory=uid)

    @property
    def cpu(self) -> str:
        return PROFILES[self.model]["cpu"]

    def validate(self) -> None:
        if not self.name.strip():
            raise ValueError("PLC 名称不能为空")
        if self.model not in PROFILES:
            raise ValueError("不支持的 PLC 型号")
        if not self.host.strip() or not 1 <= self.port <= 65535:
            raise ValueError("监听地址不能为空，端口范围为 1–65535")
        if not 0 <= self.rack <= 7 or not 0 <= self.slot <= 31:
            raise ValueError("Rack 范围为 0–7，Slot 范围为 0–31")
        if not 1 <= self.max_clients <= 256:
            raise ValueError("最大连接数范围为 1–256")
        numbers = set()
        for block in self.blocks:
            if block.number in numbers:
                raise ValueError(f"DB{block.number} 编号重复")
            numbers.add(block.number)
            block.build_memory()


@dataclass
class Project:
    name: str = "S7 Workspace"
    plcs: list[PLC] = field(default_factory=list)
    version: int = 1

    def validate(self) -> None:
        ids = set()
        endpoints = set()
        for plc in self.plcs:
            plc.validate()
            endpoint = (plc.host, plc.port)
            if any(port == plc.port and (host == plc.host or "0.0.0.0" in {host, plc.host}) for host, port in endpoints):
                raise ValueError(f"重复监听地址：{plc.host}:{plc.port}")
            endpoints.add(endpoint)
            for obj in [plc, *plc.blocks, *(var for db in plc.blocks for var in db.variables)]:
                if not obj.id or obj.id in ids:
                    raise ValueError("项目包含重复或空对象 ID")
                ids.add(obj.id)

    def save(self, path: str | Path) -> None:
        self.validate()
        path = Path(path)
        raw = json.dumps(asdict(self), ensure_ascii=False, indent=2, allow_nan=False)
        # Atomic replacement keeps the previous project intact on a failed save.
        name = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False) as file:
                name = file.name
                file.write(raw)
                file.flush()
                os.fsync(file.fileno())
            os.replace(name, path)
        finally:
            if name and os.path.exists(name):
                os.unlink(name)

    @classmethod
    def load(cls, path: str | Path) -> Project:
        path = Path(path)
        if path.stat().st_size > 10 * 1024 * 1024:
            raise ValueError("项目文件不能超过 10 MB")
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("version") != 1:
            raise ValueError("不支持的项目文件版本")
        try:
            plcs = []
            for source in data["plcs"]:
                source = dict(source)
                blocks = []
                for raw_db in source.pop("blocks", []):
                    raw_db = dict(raw_db)
                    variables = []
                    for raw_var in raw_db.pop("variables", []):
                        raw_var = dict(raw_var)
                        raw_var["simulation"] = Simulation(**raw_var.get("simulation", {}))
                        variables.append(Variable(**raw_var))
                    blocks.append(DataBlock(**raw_db, variables=variables))
                plcs.append(PLC(**source, blocks=blocks))
            project = cls(name=data["name"], plcs=plcs)
            project.validate()
            return project
        except (KeyError, TypeError, AttributeError, OverflowError) as exc:
            raise ValueError(f"项目文件格式不正确：{exc}") from exc


def demo_project() -> Project:
    return Project(plcs=[PLC(blocks=[
        DataBlock(number=1, name="Process_Data", variables=[
            Variable(name="System_Running", dtype="BOOL", value=True, comment="设备运行状态"),
            Variable(name="Emergency_Stop", dtype="BOOL", value=False, comment="急停信号"),
            Variable(name="Temperature", value=24.5, comment="反应釜温度 · °C", simulation=Simulation("sine", 20, 80, 250, 20000)),
            Variable(name="Pressure", value=4.2, comment="管道压力 · bar", simulation=Simulation("random", 3.8, 4.6, 1000)),
            Variable(name="Motor_Speed", dtype="INT", value=1450, comment="主电机转速 · rpm", simulation=Simulation("random", 1400, 1500, 1000)),
            Variable(name="Batch_Count", dtype="DINT", value=128, comment="累计批次"),
            Variable(name="Product_Name", dtype="STRING", value="S7 Demo", comment="产品标识 · STRING[32]"),
            Variable(name="Tank_Levels", dtype="REAL", count=4, value=[32.5, 60.0, 48.2, 71.0], comment="储罐液位数组 · %", simulation=Simulation("random", 20, 90, 2000)),
        ]),
        DataBlock(number=2, name="Control_Parameters", variables=[
            Variable(name="Setpoint", value=65.0, comment="温度设定值 · °C"),
            Variable(name="Valve_Open", dtype="BOOL", value=False, comment="阀门控制"),
            Variable(name="Recipe_ID", dtype="UINT", value=1001, comment="配方编号"),
        ]),
    ])])


def clone(value):
    return copy.deepcopy(value)


def available_port(plcs, host="127.0.0.1"):
    """Suggest a free endpoint; binding on start remains authoritative."""
    import socket
    used = {plc.port for plc in plcs}
    for port in range(1102, 65536):
        if port in used:
            continue
        try:
            with socket.socket() as probe:
                probe.bind((host, port))
            return port
        except OSError:
            continue
    raise ValueError("没有可用监听端口")
