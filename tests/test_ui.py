import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from s7sim.dialogs import DBDialog, PLCDialog, SimulationDialog, VariableDialog
from s7sim.models import PLC, Project, Simulation, Variable, clone, demo_project
from s7sim.widgets import STYLE
from s7sim.window import MainWindow


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    application.setStyle("Fusion")
    application.setStyleSheet(STYLE)
    return application


@pytest.fixture
def window(app, tmp_path):
    from PySide6.QtCore import QSettings
    window = MainWindow()
    window.settings = QSettings(str(tmp_path / 'ui-prefs.ini'), QSettings.Format.IniFormat)
    window.show()
    app.processEvents()
    yield window
    window.dirty = False
    window.close()
    app.processEvents()


def test_table_value_edit_save_reload_and_filter(window, app, tmp_path):
    assert window.data_table.rowCount() == 8
    window.data_table.setCurrentCell(5, 0)
    window.value_input.setText("999")
    window.write_selected_value()
    assert window.data_table.item(5, 3).text() == "999"
    window.path = tmp_path / "project.json"
    assert window.save_project()
    assert Project.load(window.path).plcs[0].blocks[0].variables[5].value == 999
    window.search.setText("Pressure")
    assert not window.data_table.isRowHidden(3)
    assert window.data_table.isRowHidden(0)
    window.search.clear()
    assert not window.data_table.isRowHidden(0)


def test_stopped_memory_survives_structure_edit(window):
    plc = window.plc()
    db = window.db()
    window.engine.runtime(plc).set_value(db, 5, 1234)
    assert window.structural_allowed()
    replacement = clone(plc)
    replacement.blocks[0].variables.append(Variable(name="extra", value=3.0))
    window.commit_plc(replacement)
    assert window.data_table.rowCount() == 9
    assert window.data_table.item(5, 3).text() == "1234"


def test_empty_project_and_all_profile_dialogs(window):
    window.replace_project(Project())
    assert not window.run_button.isEnabled()
    assert not window.add_db_button.isEnabled()
    for model in ("S7-300", "S7-400", "S7-1200", "S7-1500"):
        dialog = PLCDialog(PLC(model=model))
        assert dialog.build().model == model
        dialog.close()


def test_variable_array_and_simulation_dialogs(app):
    dialog = VariableDialog()
    dialog.name.setText("Values")
    dialog.dtype.setCurrentText("INT")
    dialog.count.setValue(3)
    dialog.value.setText("[10, 20, 30]")
    var = dialog.build()
    assert var.value == [10, 20, 30]
    simulation = SimulationDialog(var)
    simulation.mode.setCurrentIndex(simulation.mode.findData("random"))
    simulation.minimum.setText("10")
    simulation.maximum.setText("20")
    assert simulation.build().mode == "random"
    dialog.close()
    simulation.close()


def test_inline_address_and_storage_length(window, tmp_path):
    window.data_table.item(5, 2).setText("100.0")
    assert window.db().variables[5].offset == 100
    window.data_table.item(5, 6).setText("8")
    assert window.db().variables[5].storage_size == 8
    assert window.engine.runtime(window.plc()).layouts[window.db().id][6].offset == 108
    window.path = tmp_path / "manual.json"
    assert window.save_project()
    var = Project.load(window.path).plcs[0].blocks[0].variables[5]
    assert (var.offset, var.storage_size) == (100, 8)


def test_inline_type_and_string_capacity(window):
    window.data_table.item(5, 1).setText("STRING")
    assert window.db().variables[5].dtype == "STRING"
    window.data_table.item(5, 8).setText("64")
    assert window.db().variables[5].length == 64
    window.set_theme(True)
    assert window.dark_theme
    window.set_theme(False)
    assert not window.dark_theme


def test_compact_editor_has_readable_height(window, app):
    window.data_table.setCurrentCell(3, 3)
    window.data_table.editItem(window.data_table.item(3, 3))
    app.processEvents()
    from PySide6.QtWidgets import QLineEdit
    editors = window.data_table.findChildren(QLineEdit)
    assert any(editor.isVisible() and editor.height() >= 26 for editor in editors)


def test_theme_mode_actions(window):
    window.set_theme_mode("auto")
    assert window.theme_mode == "auto"
    assert window.auto_action.isChecked()
    window.set_theme_mode("dark")
    assert window.theme_mode == "dark"
    assert window.dark_theme and window.dark_action.isChecked()
    window.set_theme_mode("light")
    assert window.theme_mode == "light"
    assert not window.dark_theme and window.light_action.isChecked()


def test_help_dialog_opens(window, app):
    seen = {}

    def close_dialog():
        dialog = app.activeModalWidget()
        seen["type"] = type(dialog).__name__ if dialog is not None else None
        if dialog is not None:
            dialog.accept()

    QTimer.singleShot(150, close_dialog)
    window.show_help()
    assert seen.get("type") == "QDialog"


def test_theme_toggle_animation_keeps_its_position(window, app):
    toggle = window.theme_toggle
    before = toggle.mapTo(window, QPoint(0, 0))
    toggle.set_dark(True, animate=True)
    QTest.qWait(320)
    assert toggle.mapTo(window, QPoint(0, 0)) == before
    assert toggle.x() > window.width() // 2


def test_empty_connection_description_is_readable(window, app):
    window.tabs.setCurrentIndex(1)
    app.processEvents()
    description = window.connection_empty.text
    assert description.height() >= description.sizeHint().height()


def test_bool_selectors_and_initial_value(window, app):
    from PySide6.QtWidgets import QComboBox, QStyleOptionViewItem
    window.data_table.setCurrentCell(0, 0)
    window.value_input.boolean.setCurrentText('false')
    window.write_selected_value()
    assert window.data_table.item(0, 3).text() == 'false'
    assert window.value_input.currentIndex() == 1
    delegate = window.data_table.itemDelegate()
    index = window.data_table.model().index(0, 3)
    editor = delegate.createEditor(window.data_table, QStyleOptionViewItem(), index)
    assert isinstance(editor, QComboBox)
    delegate.setEditorData(editor, index)
    editor.setCurrentText('true')
    delegate.setModelData(editor, window.data_table.model(), index)
    assert window.engine.runtime(window.plc()).read_block(window.db())[0][0][0] is True
    editor.deleteLater()
    dialog = VariableDialog(Variable(dtype='BOOL', value=False))
    assert dialog.value.currentIndex() == 1
    dialog.value.boolean.setCurrentText('true')
    assert dialog.build().value is True
    dialog.count.setValue(2)
    assert dialog.value.currentIndex() == 0
    assert dialog.build().value == [False, False]
    dialog.close()


def test_save_as_uses_configured_folder_and_cancel_keeps_path(window, tmp_path, monkeypatch):
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QFileDialog
    window.settings = QSettings(str(tmp_path / 'prefs.ini'), QSettings.Format.IniFormat)
    window.settings.setValue('files/default_directory', str(tmp_path / '项目'))
    seen = []
    def choose(*args):
        seen.append(args[2])
        return '', ''
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', choose)
    assert not window.save_as()
    assert window.path is None
    assert str(tmp_path / '项目') in seen[0]


def test_simulation_waiting_status(window):
    window.data_table.setCurrentCell(2, 0)
    window.refresh()
    assert '等待启动服务' in window.sim_summary.text()
    assert not window.sim_start_button.isHidden()


def test_copy_uses_full_value_not_truncated_label(window, app):
    from s7sim.models import clone
    replacement = clone(window.plc())
    target = replacement.blocks[0].variables[6]
    target.length = 200
    target.value = 'x' * 150
    window.commit_plc(replacement)
    window.data_table.setCurrentCell(6, 0)
    window.copy_value()
    assert app.clipboard().text() == 'x' * 150


def test_start_simulation_action_updates_boolean_in_ui(window):
    import socket
    from s7sim.models import Simulation
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    replacement = clone(window.plc())
    replacement.port = port
    window.commit_plc(replacement)
    runtime = window.engine.runtime(window.plc())
    runtime.set_simulation(window.db(), 0, Simulation('toggle', interval_ms=100))
    window.data_table.setCurrentCell(0, 0)
    window.start_simulation()
    seen = set()
    for _ in range(12):
        QTest.qWait(40)
        window.refresh()
        seen.add(window.data_table.item(0, 3).text())
    assert seen == {'true', 'false'}
    assert '模拟中' in window.sim_summary.text()
    window.toggle_cpu()
    frozen = runtime.read_block(window.db())[0][0][0]
    QTest.qWait(250)
    assert runtime.read_block(window.db())[0][0][0] == frozen
    assert 'CPU 已暂停' in window.sim_summary.text()
    window.start_simulation()
    assert int(runtime.server.cpu_state) == 8


def test_context_delete_targets_clicked_db_even_if_selection_changes(window, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    root = window.tree.topLevelItem(0)
    keep_id, delete_id = [block.id for block in window.plc().blocks]
    menu = window.tree_menu(root.child(1))
    delete = next(action for action in menu.actions() if action.text() == '删除 DB…')
    window.tree.setCurrentItem(root.child(0))
    prompts = []
    def confirm(*args):
        prompts.append(args)
        return QMessageBox.StandardButton.Yes
    monkeypatch.setattr(QMessageBox, 'question', confirm)
    delete.trigger()
    assert [block.id for block in window.plc().blocks] == [keep_id]
    assert delete_id != window.db_id
    assert 'Control_Parameters' in prompts[0][2]
    assert prompts[0][-1] == QMessageBox.StandardButton.No
    menu.deleteLater()


def test_context_delete_cancel_preserves_project_and_empty_menu_is_safe(window, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    before = clone(window.project)
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.No)
    menu = window.tree_menu(window.tree.topLevelItem(0))
    next(a for a in menu.actions() if a.text() == '删除 PLC…').trigger()
    assert window.project == before
    empty = window.tree_menu(None)
    assert [a.text() for a in empty.actions()] == ['新增 PLC…']
    menu.deleteLater()
    empty.deleteLater()


def test_delete_key_on_plc_does_not_delete_only_its_first_db(window, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Yes)
    window.tree.setCurrentItem(window.tree.topLevelItem(0))
    window.tree.setFocus()
    QTest.keyClick(window.tree, Qt.Key.Key_Delete)
    assert not window.project.plcs
    assert window.tree.topLevelItemCount() == 0


def test_running_context_menu_disables_structure_changes(window, monkeypatch):
    runtime = window.engine.runtime(window.plc())
    with monkeypatch.context() as patch:
        patch.setattr(type(runtime), 'running', property(lambda self: True))
        root = window.tree.topLevelItem(0)
        menu = window.tree_menu(root.child(1))
        assert all(not action.isEnabled() for action in menu.actions() if not action.isSeparator())
        menu.deleteLater()
        menu = window.tree_menu(root)
        actions = {a.text(): a for a in menu.actions()}
        assert actions['停止服务'].isEnabled()
        assert not actions['PLC 配置…'].isEnabled()
        assert actions['停止并删除 PLC…'].isEnabled()
        menu.deleteLater()


def test_context_copy_uses_target_db_and_allocates_new_ids(window):
    source = window.plc().blocks[1]
    menu = window.tree_menu(window.tree.topLevelItem(0).child(1))
    next(a for a in menu.actions() if a.text() == '复制 DB').trigger()
    copied = window.db()
    assert copied.number not in [1, 2]
    assert copied.name == source.name + '_Copy'
    assert len(copied.variables) == len(source.variables)
    assert {v.id for v in copied.variables}.isdisjoint(v.id for v in source.variables)
    menu.deleteLater()


@pytest.mark.parametrize('dark', [False, True])
def test_inspector_controls_remain_inside_scroll_viewport(window, app, dark):
    from PySide6.QtWidgets import QScrollArea
    window.set_theme(dark)
    window.resize(1280, 800)
    window.data_table.setCurrentCell(2, 0)
    window.refresh()
    app.processEvents()
    scroll = window.inspector.findChild(QScrollArea)
    for control in (window.write_button, window.sim_button, window.copy_button):
        point = control.mapTo(scroll.viewport(), QPoint(control.width(), 0))
        assert point.x() <= scroll.viewport().width()
    assert window.value_input.height() == window.write_button.height()


def test_long_form_scrolls_while_footer_remains_visible(window, app):
    dialog = VariableDialog(Variable(dtype='STRING', value='demo'), window)
    dialog.show()
    dialog.resize(624, 500)
    app.processEvents()
    assert dialog.scroll.verticalScrollBar().maximum() > 0
    assert dialog.buttons.geometry().bottom() < dialog.height()
    dialog.scroll.verticalScrollBar().setValue(dialog.scroll.verticalScrollBar().maximum())
    app.processEvents()
    assert dialog.comment.mapTo(dialog.scroll.viewport(), QPoint(0, 0)).y() >= 0
    dialog.close()


def test_simulation_form_only_exposes_relevant_fields(app):
    dialog = SimulationDialog(Variable(dtype='BOOL', value=False))
    dialog.mode.setCurrentIndex(dialog.mode.findData('toggle'))
    assert dialog.form.isRowVisible(dialog.interval_row)
    assert not dialog.form.isRowVisible(dialog.bounds_row)
    assert not dialog.form.isRowVisible(dialog.period_row)
    dialog.mode.setCurrentIndex(dialog.mode.findData('manual'))
    assert not dialog.form.isRowVisible(dialog.interval_row)
    dialog.close()


def test_keyboard_context_menu_opens_for_selected_db(window, app):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QMenu
    target = window.tree.topLevelItem(0).child(1)
    window.tree.setCurrentItem(target)
    window.tree.setFocus()
    QTest.keyClick(window.tree, Qt.Key.Key_F10, Qt.KeyboardModifier.ShiftModifier)
    menu = app.activePopupWidget()
    assert isinstance(menu, QMenu)
    assert menu.actions()[0].text() == target.text(0)
    assert any(action.text() == '删除 DB…' for action in menu.actions())
    menu.close()
