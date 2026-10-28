import math
import struct

import pytest

from s7sim.codec import Layout, default_value, make_layout, parse_input, read_value, write_value
from s7sim.models import DataBlock, Variable


@pytest.mark.parametrize("dtype,value", [
    ("BOOL", True), ("BYTE", 255), ("SINT", -128), ("USINT", 255),
    ("WORD", 65535), ("INT", -32768), ("UINT", 65535),
    ("DWORD", 2**32 - 1), ("DINT", -2**31), ("UDINT", 2**32 - 1),
    ("LWORD", 2**64 - 1), ("LINT", -2**63), ("ULINT", 2**64 - 1),
    ("REAL", 24.5), ("LREAL", math.pi), ("CHAR", "Z"), ("WCHAR", "温"),
    ("STRING", "Grüße"), ("WSTRING", "温度😀"), ("TIME", -12345),
    ("TOD", 86_399_999), ("DATE", 13300), ("DATE_AND_TIME", "2026-10-23T12:34:56.789"),
])
def test_scalar_and_array_roundtrip(dtype, value):
    for count in (1, 3):
        expected = value if count == 1 else [value] * count
        var = Variable(dtype=dtype, count=count, value=expected)
        db = DataBlock(variables=[var])
        memory = db.build_memory()
        layout = make_layout(db.variables, db.size)[0][0]
        assert read_value(memory, layout) == expected


def test_bool_packing_alignment_and_big_endian():
    variables = [Variable(name="flags", dtype="BOOL", count=10, value=[True] * 10),
                 Variable(name="bit", dtype="BOOL", value=True),
                 Variable(name="value", dtype="INT", value=0x1234),
                 Variable(name="float", dtype="REAL", value=1.0)]
    db = DataBlock(variables=variables)
    memory = db.build_memory()
    layouts, used = make_layout(variables, db.size)
    assert [(a.offset, a.bit) for a in layouts] == [(0, 0), (1, 2), (2, 0), (4, 0)]
    assert memory[:8] == b"\xff\x07\x12\x34\x3f\x80\x00\x00"
    assert layouts[1].address(12) == "DB12.DBX1.2"
    assert used == 8


def test_array_write_validation_is_atomic():
    db = DataBlock(variables=[Variable(dtype="INT", count=3, value=[1, 2, 3])])
    memory = db.build_memory()
    original = bytes(memory)
    layout = make_layout(db.variables, db.size)[0][0]
    with pytest.raises(ValueError):
        write_value(memory, layout, [4, 5, 40000])
    assert bytes(memory) == original


@pytest.mark.parametrize("dtype,value", [("BOOL", "false"), ("INT", 32768), ("UINT", -1), ("REAL", math.nan), ("LREAL", math.inf), ("CHAR", "AB"), ("WCHAR", "😀"), ("STRING", "中文"), ("DATE_AND_TIME", "2090-01-01")])
def test_invalid_values_rejected(dtype, value):
    with pytest.raises((ValueError, UnicodeError, OverflowError, struct.error)):
        DataBlock(variables=[Variable(dtype=dtype, value=value)]).build_memory()


def test_string_capacity_and_header():
    var = Variable(dtype="STRING", length=5, value="abc")
    db = DataBlock(variables=[var])
    assert db.build_memory()[:7] == b"\x05\x03abc\x00\x00"
    var.value = "abcdef"
    with pytest.raises(ValueError):
        db.build_memory()


def test_capacity_duplicate_names_and_default_values():
    with pytest.raises(ValueError, match="超出"):
        DataBlock(size=2, variables=[Variable(dtype="REAL", value=0.0)]).build_memory()
    with pytest.raises(ValueError, match="重复"):
        make_layout([Variable(name="x"), Variable(name="x")], 512)
    assert default_value("BOOL", 3) == [False, False, False]
    assert parse_input("2026-10-23", "DATE") == 13444
    assert parse_input("0xFF", "WORD") == 255
    assert parse_input("false", "BOOL") is False
    assert parse_input("[1, 2]", "INT", 2) == [1, 2]


def test_manual_offsets_padding_and_collision():
    variables = [Variable(name="flag", dtype="BOOL", value=True, offset=0, bit_offset=3),
                 Variable(name="sensor", dtype="REAL", value=12.5, offset=20, storage_size=8),
                 Variable(name="next", dtype="INT", value=123)]
    db = DataBlock(variables=variables)
    layouts, used = make_layout(variables, 512)
    memory = db.build_memory()
    assert memory[0] == 8
    assert layouts[1].offset == 20
    assert layouts[2].offset == 28
    assert used == 30
    assert struct.unpack_from(">f", memory, 20)[0] == 12.5
    variables[2].offset = 24
    with pytest.raises(ValueError, match="重叠"):
        db.build_memory()
    variables[2].offset = 30
    variables[1].storage_size = 2
    with pytest.raises(ValueError, match="长度不足"):
        db.build_memory()
