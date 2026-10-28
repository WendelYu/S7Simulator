import csv
import io

from s7sim.models import PLC, clone
from s7sim.point_import import HEADERS, parse_points, template_text, read_source


def test_template_multiple_dbs_and_no_mutation():
    plc = PLC()
    original = clone(plc)
    result = parse_points(template_text(), plc)
    assert not result.errors
    assert len(result.rows) == 4
    assert result.new_blocks == 2
    assert plc == original
    result.plc.validate()
    assert result.plc.blocks[0].variables[2].value == '测试产品'


def test_duplicate_existing_is_rejected():
    first = parse_points(template_text(), PLC())
    original = clone(first.plc)
    result = parse_points(template_text(), first.plc)
    assert len(result.errors) == 4
    assert first.plc == original


def test_tsv_paste_and_defaults():
    result = parse_points('DB编号\t变量名\t数据类型\n1\tTemperature\tREAL\n1\tLabel\tSTRING\n', PLC())
    assert not result.errors
    assert result.plc.blocks[0].variables[1].length == 32


def test_overlap_and_line_errors():
    result = parse_points('DB编号,变量名,数据类型,偏移\n1,A,REAL,20.0\n1,B,INT,22.0\n1,C,INVALID,\n', PLC())
    assert len(result.errors) == 2
    assert '第 3 行' in result.errors[0]
    assert '重叠' in result.errors[0]


def test_malformed_header_and_missing_columns():
    assert parse_points('Name,Type\nx,REAL', PLC()).errors
    assert parse_points('DB编号,变量名,数据类型\n1,A', PLC()).errors
    assert parse_points('', PLC()).errors


def test_bom_file(tmp_path):
    path = tmp_path / 'points.csv'
    path.write_text(template_text(), encoding='utf-8-sig')
    assert not parse_points(read_source(path), PLC()).errors


def test_preview_disables_import_after_edit():
    import os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication
    from s7sim.import_dialog import PointImportDialog
    app = QApplication.instance() or QApplication([])
    dialog = PointImportDialog(PLC())
    dialog.source.setPlainText(template_text())
    dialog.preview()
    assert dialog.apply.isEnabled()
    dialog.source.setPlainText('invalid')
    assert not dialog.apply.isEnabled()
    assert dialog.result_value is None
    dialog.close()
