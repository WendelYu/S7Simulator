"""Transactional point import. Parsing never modifies the active PLC."""
import csv
import io
from dataclasses import dataclass
from pathlib import Path

from .codec import INT_LIMITS, TYPES, default_value, make_layout, parse_input
from .models import DataBlock, PLC, Simulation, Variable, clone

HEADERS = ['DB编号', 'DB名称', 'DB容量', '变量名', '数据类型', '偏移', '数组数量', '字符串容量', '预留字节', '初始值', '模拟模式', '下限', '上限', '间隔ms', '周期ms', '注释']
MODES = {'手动': 'manual', '随机': 'random', '正弦': 'sine', '斜坡': 'ramp', '翻转': 'toggle'}


def template_text():
    out = io.StringIO(newline='')
    writer = csv.writer(out)
    writer.writerow(HEADERS)
    writer.writerows([
        [10, 'Test_Process', 512, 'Running', 'BOOL', '0.0', 1, '', '', 'true', '翻转', '', '', 1000, '', '运行信号'],
        [10, 'Test_Process', 512, 'Temperature', 'REAL', '2.0', 1, '', '', 25.5, '随机', 20, 80, 500, '', '温度'],
        [10, 'Test_Process', 512, 'Product', 'WSTRING', '', 1, 32, '', '测试产品', '手动', '', '', '', '', '中文名称'],
        [11, 'Test_Array', 512, 'Levels', 'REAL', '', 4, '', '', '[10, 20, 30, 40]', '随机', 0, 100, 1000, '', '液位数组'],
    ])
    return out.getvalue()


def save_template(path):
    Path(path).write_text(template_text(), encoding='utf-8-sig')


def read_source(path):
    raw = Path(path).read_bytes()
    if len(raw) > 5 * 1024 * 1024:
        raise ValueError('导入文件不能超过 5 MB')
    try:
        return raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        return raw.decode('gb18030')


@dataclass
class ImportResult:
    plc: PLC
    rows: list
    errors: list
    new_blocks: int


def parse_points(text, plc):
    candidate = clone(plc)
    rows, errors = [], []
    before = len(candidate.blocks)
    if len(text) > 5 * 1024 * 1024:
        return ImportResult(candidate, [], ['内容不能超过 5 MB'], 0)
    source = text.lstrip('\ufeff')
    first = source.splitlines()[0] if source.splitlines() else ''
    reader = csv.DictReader(io.StringIO(source), delimiter='\t' if '\t' in first else ',')
    if not reader.fieldnames:
        return ImportResult(candidate, [], ['内容为空，请保留模板标题行'], 0)
    reader.fieldnames = [h.strip() for h in reader.fieldnames]
    missing = set(['DB编号', '变量名', '数据类型']) - set(reader.fieldnames)
    unknown = set(reader.fieldnames) - set(HEADERS)
    if missing or unknown or len(set(reader.fieldnames)) != len(reader.fieldnames):
        return ImportResult(candidate, [], [f'标题错误。缺少：{", ".join(sorted(missing)) or "无"}；未知：{", ".join(sorted(unknown)) or "无"}。请使用模板且不要重复标题。'], 0)
    try:
        for index, raw in enumerate(reader, 2):
            if index > 10001:
                errors.append('单次最多导入 10000 个点位')
                break
            if not any(raw.values()):
                continue
            try:
                if None in raw or any(v is None for v in raw.values()):
                    raise ValueError('列数不匹配；含逗号的数组或文本请使用 CSV 引号')
                row = {k: v.strip() for k, v in raw.items()}
                number = int(row['DB编号'])
                db = next((d for d in candidate.blocks if d.number == number), None)
                size = int(row.get('DB容量') or (db.size if db else 512))
                name = row.get('DB名称') or (db.name if db else f'Data_Block_{number}')
                if db and (size != db.size or name != db.name):
                    raise ValueError(f'DB{number} 名称/容量与已有定义不一致')
                target = clone(db) if db else DataBlock(number=number, name=name, size=size)
                dtype = row['数据类型'].upper()
                if dtype not in TYPES:
                    raise ValueError(f'未知数据类型 {dtype}')
                count = int(row.get('数组数量') or 1)
                if not 1 <= count <= 4096:
                    raise ValueError('数组数量必须在 1–4096 之间')
                length = int(row.get('字符串容量') or 32)
                address = row.get('偏移', '')
                parts = address.split('.')
                if len(parts) > 2:
                    raise ValueError('偏移格式应为 字节.位，例如 20.0')
                mode = row.get('模拟模式') or 'manual'
                mode = MODES.get(mode, mode.lower())
                numeric = int if dtype in INT_LIMITS else float
                simulation = Simulation(mode, numeric(row.get('下限') or '0'), numeric(row.get('上限') or '100'), int(row.get('间隔ms') or 1000), int(row.get('周期ms') or 10000))
                var = Variable(name=row['变量名'], dtype=dtype, count=count, length=length,
                    offset=int(parts[0]) if address else None, bit_offset=int(parts[1]) if len(parts) == 2 else 0,
                    storage_size=int(row['预留字节']) if row.get('预留字节') else None,
                    value=parse_input(row['初始值'], dtype, count) if row.get('初始值') else default_value(dtype, count),
                    simulation=simulation, comment=row.get('注释', ''))
                target.variables.append(var)
                target.build_memory()
                layout = make_layout(target.variables, target.size)[0][-1]
                if db:
                    candidate.blocks[candidate.blocks.index(db)] = target
                else:
                    candidate.blocks.append(target)
                rows.append([index, f'DB{number}', var.name, dtype, layout.address(number), count, mode])
            except (ValueError, TypeError, OverflowError) as exc:
                errors.append(f'第 {index} 行：{exc}')
    except csv.Error as exc:
        errors.append(f'CSV 格式错误：{exc}')
    if not rows and not errors:
        errors.append('没有可导入的点位')
    return ImportResult(candidate, rows, errors, len(candidate.blocks) - before)
