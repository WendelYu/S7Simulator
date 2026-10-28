"""Standard (non-optimized) Siemens DB layout and big-endian value codecs."""

from __future__ import annotations

import datetime as dt
import json
import math
import struct
from dataclasses import dataclass
from typing import Any


FORMATS = {
    "BYTE": "B", "USINT": "B", "SINT": "b", "CHAR": "c",
    "WORD": "H", "UINT": "H", "INT": "h", "WCHAR": "H",
    "DWORD": "I", "UDINT": "I", "DINT": "i", "TIME": "i", "TOD": "I",
    "LWORD": "Q", "ULINT": "Q", "LINT": "q", "REAL": "f", "LREAL": "d",
    "DATE": "H",
}
TYPES = ("BOOL", *FORMATS, "STRING", "WSTRING", "DATE_AND_TIME")
INT_LIMITS = {
    "BYTE": (0, 255), "USINT": (0, 255), "SINT": (-128, 127),
    "WORD": (0, 65535), "UINT": (0, 65535), "INT": (-32768, 32767),
    "DWORD": (0, 2**32 - 1), "UDINT": (0, 2**32 - 1),
    "DINT": (-2**31, 2**31 - 1), "TIME": (-2**31, 2**31 - 1),
    "TOD": (0, 86_399_999), "LWORD": (0, 2**64 - 1), "ULINT": (0, 2**64 - 1),
    "LINT": (-2**63, 2**63 - 1), "DATE": (0, 65535),
}
NUMERIC = set(INT_LIMITS) | {"REAL", "LREAL"}
EPOCH = dt.date(1990, 1, 1)


@dataclass(frozen=True)
class Layout:
    offset: int
    bit: int
    size: int
    count: int
    dtype: str

    def address(self, db: int) -> str:
        if self.dtype == "BOOL":
            return f"DB{db}.DBX{self.offset}.{self.bit}"
        prefix = {1: "B", 2: "W", 4: "D"}.get(self.size, "B")
        return f"DB{db}.DB{prefix}{self.offset}"


def item_size(dtype: str, length: int = 32) -> int:
    if dtype == "BOOL":
        return 1
    if dtype == "STRING":
        if not 1 <= length <= 254:
            raise ValueError("STRING 最大长度必须在 1–254 之间")
        return length + 2
    if dtype == "WSTRING":
        if not 1 <= length <= 16382:
            raise ValueError("WSTRING 最大长度必须在 1–16382 之间")
        return length * 2 + 4
    if dtype == "DATE_AND_TIME":
        return 8
    if dtype not in FORMATS:
        raise ValueError(f"未知数据类型：{dtype}")
    return struct.calcsize(">" + FORMATS[dtype])


def make_layout(variables: list, capacity: int) -> tuple[list[Layout], int]:
    cursor = 0
    result, occupied, names = [], [], set()
    for var in variables:
        if not var.name.strip() or var.name in names:
            raise ValueError("变量名不能为空或重复")
        names.add(var.name)
        if not 1 <= var.count <= 4096:
            raise ValueError("数组元素数量必须在 1–4096 之间")
        size = item_size(var.dtype, var.length)
        natural = var.count if var.dtype == "BOOL" else size * var.count * 8
        if var.offset is not None:
            if type(var.offset) is not int or var.offset < 0 or not 0 <= var.bit_offset <= 7:
                raise ValueError("偏移必须为非负字节地址，位偏移为 0–7")
            if var.dtype != "BOOL" and var.bit_offset:
                raise ValueError("只有 BOOL 支持非零位偏移")
            start = var.offset * 8 + var.bit_offset
        elif var.dtype == "BOOL":
            start = cursor
        else:
            byte = (cursor + 7) // 8
            if size > 1 and byte % 2:
                byte += 1
            start = byte * 8
        span = natural
        if var.storage_size is not None:
            if type(var.storage_size) is not int or var.storage_size < 1 or var.storage_size * 8 < natural:
                raise ValueError(f"{var.name} 的预留长度不足，至少需要 {(natural + 7) // 8} 字节")
            span = var.storage_size * 8
        end = start + span
        for left, right, name in occupied:
            if start < right and end > left:
                raise ValueError(f"{var.name} 与 {name} 地址重叠")
        occupied.append((start, end, var.name))
        result.append(Layout(start // 8, start % 8, size, var.count, var.dtype))
        cursor = max(cursor, end)
    used = (cursor + 7) // 8
    if used > capacity:
        raise ValueError(f"变量需要 {used} 字节，超出 DB 容量 {capacity} 字节")
    return result, used


def default_value(dtype: str, count: int = 1) -> Any:
    value = False if dtype == "BOOL" else "" if dtype in {"STRING", "WSTRING"} else "A" if dtype in {"CHAR", "WCHAR"} else "2026-01-01T00:00:00" if dtype == "DATE_AND_TIME" else 0
    return [value for _ in range(count)] if count > 1 else value


def parse_input(text: str, dtype: str, count: int = 1) -> Any:
    if count > 1:
        value = json.loads(text)
        if not isinstance(value, list) or len(value) != count:
            raise ValueError(f"请输入包含 {count} 个元素的 JSON 数组")
        return value
    if dtype == "BOOL":
        if text.lower() not in {"true", "false", "1", "0"}:
            raise ValueError("BOOL 请输入 true、false、1 或 0")
        return text.lower() in {"true", "1"}
    if dtype in INT_LIMITS:
        if dtype == "DATE" and "-" in text[1:]:
            return (dt.date.fromisoformat(text) - EPOCH).days
        return int(text, 16) if text.lower().startswith(("0x", "-0x")) else int(text)
    if dtype in {"REAL", "LREAL"}:
        return float(text)
    return text


def _encode(dtype: str, value: Any, length: int) -> bytes:
    if dtype in {"STRING", "WSTRING"}:
        if not isinstance(value, str):
            raise ValueError("字符串值必须是文本")
        raw = value.encode("latin-1" if dtype == "STRING" else "utf-16-be")
        units = len(raw) if dtype == "STRING" else len(raw) // 2
        if units > length:
            raise ValueError(f"字符串超过最大长度 {length}")
        header = bytes([length, units]) if dtype == "STRING" else struct.pack(">HH", length, units)
        return header + raw + bytes(length * (1 if dtype == "STRING" else 2) - len(raw))
    if dtype == "DATE_AND_TIME":
        value = dt.datetime.fromisoformat(str(value))
        if not 1990 <= value.year <= 2089:
            raise ValueError("DATE_AND_TIME 年份范围为 1990–2089")
        bcd = lambda n: (n // 10 << 4) | (n % 10)
        ms = value.microsecond // 1000
        return bytes([bcd(value.year % 100), bcd(value.month), bcd(value.day), bcd(value.hour), bcd(value.minute), bcd(value.second), bcd(ms // 10), ((ms % 10) << 4) | (value.isoweekday() % 7 + 1)])
    if dtype == "CHAR":
        raw = str(value).encode("latin-1")
        if len(raw) != 1:
            raise ValueError("CHAR 必须是一个 Latin-1 字符")
        return raw
    if dtype == "WCHAR":
        raw = str(value).encode("utf-16-be")
        if len(raw) != 2:
            raise ValueError("WCHAR 必须是一个 UTF-16 码元")
        return raw
    if dtype in INT_LIMITS:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{dtype} 必须为整数")
        low, high = INT_LIMITS[dtype]
        if not low <= value <= high:
            raise ValueError(f"{dtype} 范围为 {low}–{high}")
    if dtype in {"REAL", "LREAL"}:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("浮点值必须为有限数值")
    return struct.pack(">" + FORMATS[dtype], value)


def write_value(memory: bytearray, layout: Layout, value: Any, length: int = 32) -> None:
    values = value if layout.count > 1 else [value]
    if not isinstance(values, list) or len(values) != layout.count:
        raise ValueError(f"需要 {layout.count} 个数组元素")
    # Validate every element before changing any bytes (atomic at variable level).
    if layout.dtype == "BOOL":
        if any(not isinstance(v, bool) and not (type(v) is int and v in (0, 1)) for v in values):
            raise ValueError("BOOL 只接受 true/false 或 0/1")
        for i, v in enumerate(values):
            index, bit = divmod(layout.offset * 8 + layout.bit + i, 8)
            memory[index] = (memory[index] & ~(1 << bit)) | (int(v) << bit)
    else:
        raw = b"".join(_encode(layout.dtype, v, length) for v in values)
        memory[layout.offset:layout.offset + len(raw)] = raw


def read_value(memory: bytearray, layout: Layout) -> Any:
    values = []
    for i in range(layout.count):
        offset = layout.offset + i * layout.size
        dtype = layout.dtype
        if dtype == "BOOL":
            index, bit = divmod(layout.offset * 8 + layout.bit + i, 8)
            value = bool(memory[index] & (1 << bit))
        elif dtype in {"STRING", "WSTRING"}:
            if dtype == "STRING":
                n = min(memory[offset + 1], layout.size - 2)
                value = bytes(memory[offset + 2:offset + 2 + n]).decode("latin-1")
            else:
                n = min(int.from_bytes(memory[offset + 2:offset + 4], "big"), (layout.size - 4) // 2)
                value = bytes(memory[offset + 4:offset + 4 + n * 2]).decode("utf-16-be", errors="replace")
        elif dtype == "DATE_AND_TIME":
            raw = memory[offset:offset + 8]
            unbcd = lambda n: (n >> 4) * 10 + (n & 15)
            year = unbcd(raw[0])
            value = dt.datetime(1900 + year if year >= 90 else 2000 + year, *[unbcd(x) for x in raw[1:6]], (unbcd(raw[6]) * 10 + (raw[7] >> 4)) * 1000).isoformat(timespec="milliseconds")
        elif dtype in {"CHAR", "WCHAR"}:
            value = bytes(memory[offset:offset + layout.size]).decode("latin-1" if dtype == "CHAR" else "utf-16-be", errors="replace")
        else:
            value = struct.unpack_from(">" + FORMATS[dtype], memory, offset)[0]
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("浮点内存包含 NaN 或 Infinity")
        values.append(value)
    return values if layout.count > 1 else values[0]


def display_value(value: Any) -> str:
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        return format(value, ".7g")
    return str(value)
