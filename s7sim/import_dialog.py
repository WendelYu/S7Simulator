from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog, QPlainTextEdit, QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView)
from . import icons, motion
from .theme import current
from .widgets import IconTile
from .point_import import parse_points, read_source, save_template


class PointImportDialog(QDialog):
    def __init__(self, plc, parent=None):
        super().__init__(parent)
        self.plc = plc
        self.result_value = None
        self.setWindowTitle('批量导入点位')
        self.resize(960, 740)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        header = QHBoxLayout()
        header.setSpacing(13)
        header.addWidget(IconTile('download', 'accent', 42))
        titles = QVBoxLayout()
        titles.setSpacing(3)
        heading = QLabel('批量导入点位')
        heading.setObjectName('dialogTitle')
        titles.addWidget(heading)
        destination = QLabel(f'目标控制器 · {plc.name}')
        destination.setTextFormat(Qt.TextFormat.PlainText)
        destination.setObjectName('dialogSubtitle')
        titles.addWidget(destination)
        header.addLayout(titles, 1)
        layout.addLayout(header)
        note = QLabel('导入到当前 PLC。支持模板 CSV，或从 Excel 复制含标题的单元格后粘贴。\n同一 DB 追加点位；不存在的 DB 自动创建。重复名称、地址重叠或任一错误都会阻止整批导入。')
        note.setObjectName('dialogSubtitle')
        note.setWordWrap(True)
        layout.addWidget(note)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        for text, glyph, handler in [('保存 CSV 模板', 'download', self.template), ('打开 CSV…', 'folder', self.open_file), ('校验并预览', 'check', self.preview)]:
            if glyph == 'check':
                actions.addStretch(1)
            button = QPushButton(text)
            button.setIcon(icons.make_icon(glyph, current().text_muted, 15))
            button.setFixedHeight(38)
            button.setAutoDefault(False)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            if glyph == 'check':
                button.setObjectName('softButton')
            button.clicked.connect(handler)
            actions.addWidget(button)
        layout.addLayout(actions)
        self.source = QPlainTextEdit()
        self.source.setObjectName('importSource')
        self.source.setAccessibleName('待导入的 CSV 或 TSV 点位数据')
        self.source.setTabChangesFocus(True)
        self.source.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.source.setPlaceholderText('打开模板文件，或将带标题的点位数据粘贴到这里…')
        self.source.setMinimumHeight(96)
        self.source.setMaximumHeight(150)
        self.source.textChanged.connect(self.invalidate)
        layout.addWidget(self.source)
        self.summary = QLabel('等待导入数据')
        self.summary.setObjectName('simPreview')
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(['源行', 'DB', '变量名', '类型', '实际地址', '数量', '模拟'])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setWordWrap(False)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.table.horizontalHeader().setFixedHeight(38)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)
        self.errors = QPlainTextEdit()
        self.errors.setObjectName('importErrors')
        self.errors.setAccessibleName('导入校验错误')
        self.errors.setReadOnly(True)
        self.errors.setMaximumHeight(130)
        self.errors.hide()
        layout.addWidget(self.errors)
        footer = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        footer.rejected.connect(self.reject)
        footer.accepted.connect(self.accept)
        footer.button(QDialogButtonBox.StandardButton.Cancel).setText('取消')
        self.apply = footer.button(QDialogButtonBox.StandardButton.Ok)
        self.apply.setText('确认导入')
        self.apply.setIcon(icons.make_icon('check', current().on_accent, 15))
        self.apply.setObjectName('primary')
        self.apply.setEnabled(False)
        for button in footer.buttons():
            button.setMinimumWidth(96)
            button.setFixedHeight(38)
        layout.addWidget(footer)

    def showEvent(self, event):
        available = self.screen().availableGeometry().adjusted(16, 32, -16, -16)
        self.resize(min(960, available.width()), min(740, available.height()))
        self.move(available.center() - self.rect().center())
        motion.fade_window(self, 170)
        super().showEvent(event)

    def invalidate(self):
        self.result_value = None
        self.apply.setEnabled(False)
        self.summary.setText('内容已修改，请重新校验预览')
        self.table.setRowCount(0)
        self.errors.hide()

    def template(self):
        path, _ = QFileDialog.getSaveFileName(self, '保存模板', 'S7点位模板.csv', 'CSV (*.csv)')
        if path:
            try:
                save_template(path)
                self.summary.setText(f'模板已保存：{path}')
            except OSError as exc:
                self.summary.setText(str(exc))

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, '导入点位', '', '点位文件 (*.csv *.tsv *.txt)')
        if path:
            try:
                self.source.setPlainText(read_source(path))
                self.preview()
            except (OSError, ValueError) as exc:
                self.invalidate()
                self.summary.setText(str(exc))

    def preview(self):
        result = parse_points(self.source.toPlainText(), self.plc)
        self.table.setRowCount(min(len(result.rows), 500))
        for r, row in enumerate(result.rows[:500]):
            for c, value in enumerate(row):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                self.table.setItem(r, c, item)
        self.errors.setPlainText('\n'.join(result.errors))
        self.errors.setVisible(bool(result.errors))
        self.summary.setText(f'{len(result.rows)} 个有效点位 · 新建 {result.new_blocks} 个 DB · {len(result.errors)} 个错误（预览最多 500 行）')
        self.result_value = result.plc if not result.errors else None
        self.apply.setEnabled(self.result_value is not None)
