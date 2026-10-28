from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QFrame, QHBoxLayout,
    QLabel, QLayout, QLineEdit, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from . import icons, motion
from .value_editor import ValueEditor
from .inputs import ChoiceBox, NumberBox
from .codec import INT_LIMITS, NUMERIC, TYPES, default_value, display_value, parse_input
from .models import PROFILES, DataBlock, PLC, Simulation, Variable, clone
from .theme import current
from .widgets import HintBar, IconTile

MODE_NAMES = {"manual": "手动赋值", "random": "随机值", "sine": "正弦波", "ramp": "递增斜坡", "toggle": "定时翻转"}


class FormScrollArea(QScrollArea):
    def sizeHint(self):  # noqa: N802
        return self.widget().sizeHint() + QSize(12, 2)


def spin(low, high, value, suffix=""):
    widget = NumberBox()
    widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    widget.setRange(low, high)
    widget.setValue(value)
    widget.setSuffix(suffix)
    widget.setMinimumWidth(100)
    widget.setFixedHeight(38)
    return widget


class FormDialog(QDialog):
    """Shared shell for the four editors.

    The form keeps the original public attributes used by the rest of the app,
    but wraps them in a quieter header + card + note layout. Validation messages
    appear inline instead of interrupting with a modal message box.
    """

    def __init__(self, title, parent=None, icon="settings", subtitle=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setObjectName("formDialog")
        self.setMinimumWidth(624)
        self.setModal(True)
        self.setSizeGripEnabled(False)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.result_value = None
        self._shown_once = False
        self.colors = current()

        self.outer = QVBoxLayout(self)
        self.outer.setContentsMargins(24, 22, 24, 20)
        self.outer.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(13)
        self.header_icon = IconTile(icon, "accent", 42)
        header.addWidget(self.header_icon, 0, Qt.AlignmentFlag.AlignTop)
        title_col = QVBoxLayout()
        title_col.setSpacing(3)
        heading = QLabel(title)
        heading.setObjectName("dialogTitle")
        title_col.addWidget(heading)
        self.subtitle = QLabel(subtitle)
        self.subtitle.setObjectName("dialogSubtitle")
        self.subtitle.setWordWrap(True)
        self.subtitle.setVisible(bool(subtitle))
        title_col.addWidget(self.subtitle)
        header.addLayout(title_col, 1)
        self.outer.addLayout(header)

        self.card = QFrame()
        self.card.setObjectName("dialogCard")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(22, 16, 22, 16)
        card_layout.setSpacing(10)
        card_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.form = QFormLayout()
        self.form.setContentsMargins(0, 0, 0, 0)
        self.form.setHorizontalSpacing(18)
        self.form.setVerticalSpacing(10)
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        self.form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        card_layout.addLayout(self.form)
        self.scroll = FormScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidget(self.card)
        self.outer.addWidget(self.scroll, 1)

        self.error_bar = QFrame()
        self.error_bar.setObjectName("dialogError")
        error_layout = QHBoxLayout(self.error_bar)
        error_layout.setContentsMargins(11, 8, 11, 8)
        error_layout.setSpacing(8)
        self.error_icon = QLabel()
        self.error_icon.setFixedSize(16, 16)
        self.error_icon.setPixmap(icons.make_pixmap("alert", current().danger, 16))
        error_layout.addWidget(self.error_icon, 0, Qt.AlignmentFlag.AlignTop)
        self.error_label = QLabel("")
        self.error_label.setObjectName("dialogErrorText")
        self.error_label.setWordWrap(True)
        error_layout.addWidget(self.error_label, 1)
        self.error_bar.hide()
        self.outer.addWidget(self.error_bar)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok.setText("确定")
        ok.setObjectName("primary")
        ok.setIcon(icons.make_icon("check", current().on_accent, 15))
        ok.setDefault(True)
        cancel = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel.setText("取消")
        cancel.setIcon(icons.make_icon("x", current().text_muted, 14))
        for button in (ok, cancel):
            button.setMinimumWidth(96)
            button.setFixedHeight(38)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.buttons.accepted.connect(self.submit)
        self.buttons.rejected.connect(self.reject)
        self.outer.addWidget(self.buttons)

        self.note_bar = None

    # -- layout helpers -------------------------------------------------
    def row(self, text, widget, hint=""):
        if isinstance(widget, (QLineEdit, QComboBox, QSpinBox, ValueEditor)):
            widget.setFixedHeight(38)
        widget.setAccessibleName(text)
        field = widget
        if hint:
            wrap = QWidget()
            wrap_layout = QVBoxLayout(wrap)
            wrap_layout.setContentsMargins(0, 0, 0, 0)
            wrap_layout.setSpacing(3)
            wrap_layout.addWidget(widget)
            hint_label = QLabel(hint)
            hint_label.setObjectName("fieldHint")
            hint_label.setWordWrap(True)
            wrap_layout.addWidget(hint_label)
            field = wrap
        label = QLabel(text)
        label.setObjectName("formLabel")
        label.setMinimumWidth(102)
        label.setFixedHeight(38)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        label.setBuddy(widget)
        self.form.addRow(label, field)
        return widget

    def section(self, text):
        label = QLabel(text)
        label.setObjectName("formSection")
        self.form.addRow(label)

    def note(self, text):
        if self.note_bar is None:
            self.note_bar = HintBar(text, "accent")
            index = self.outer.indexOf(self.error_bar)
            self.outer.insertWidget(index, self.note_bar)
        else:
            self.note_bar.setText(text)

    # -- validation -----------------------------------------------------
    def show_error(self, message):
        self.error_label.setText(message)
        first = not self.error_bar.isVisible()
        self.error_bar.show()
        if first:
            motion.fade_in(self.error_bar, 150)
        if self.isVisible():
            self.fit_to_screen()
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setFocus()

    def submit(self):
        try:
            self.result_value = self.build()
            self.accept()
        except (ValueError, TypeError, OverflowError, UnicodeError) as exc:
            self.show_error(str(exc))

    # -- presentation ---------------------------------------------------
    def fit_to_screen(self, center=False):
        available = self.screen().availableGeometry().adjusted(16, 32, -16, -16)
        self.setMinimumWidth(min(624, available.width()))
        desired = self.sizeHint().expandedTo(self.minimumSizeHint())
        self.resize(min(desired.width(), available.width()), min(desired.height(), available.height()))
        if center:
            parent = self.parentWidget()
            bounds = parent.window().frameGeometry() if parent else available
            self.move(bounds.center() - self.rect().center())
        self.move(max(available.left(), min(self.x(), available.right() - self.width() + 1)),
                  max(available.top(), min(self.y(), available.bottom() - self.height() + 1)))

    def showEvent(self, event):  # noqa: N802
        if not self._shown_once:
            self._shown_once = True
            self.fit_to_screen(center=True)
            motion.fade_window(self, 170)
        super().showEvent(event)


class PLCDialog(FormDialog):
    def __init__(self, plc: PLC, parent=None):
        super().__init__(
            "PLC 配置", parent, "cpu",
            "编辑控制器的身份、网络端点与客户端上限。",
        )
        self.original = plc
        self.name = QLineEdit(plc.name)
        self.name.setClearButtonEnabled(True)
        self.model = ChoiceBox()
        self.model.addItems(PROFILES)
        self.model.setCurrentText(plc.model)
        self.cpu = QLabel(plc.cpu)
        self.cpu.setObjectName("readonly")
        self.cpu.setFixedHeight(38)
        self.host = QLineEdit(plc.host)
        self.port = spin(1, 65535, plc.port)
        self.rack = spin(0, 7, plc.rack)
        self.slot = spin(0, 31, plc.slot)
        self.clients = spin(1, 256, plc.max_clients)

        self.section("控制器")
        self.row("名称", self.name)
        self.row("型号预设", self.model)
        self.row("CPU 参考", self.cpu)

        self.section("网络与连接")
        self.row("监听 IPv4", self.host, "127.0.0.1 仅本机；0.0.0.0 允许局域网连接。")
        self.row("TCP 端口", self.port)
        rack_slot = QWidget()
        rack_layout = QHBoxLayout(rack_slot)
        rack_layout.setContentsMargins(0, 0, 0, 0)
        rack_layout.setSpacing(7)
        rack_layout.addWidget(self.rack, 1)
        rack_layout.addWidget(QLabel("/"))
        rack_layout.addWidget(self.slot, 1)
        self.rack.setAccessibleName("Rack")
        self.slot.setAccessibleName("Slot")
        self.row("Rack / Slot", rack_slot, "随型号预设更新，可按实际机架调整。")
        self.row("最大连接数", self.clients)

        self.model.currentTextChanged.connect(self.profile_changed)
        self.note(
            "模拟经典 S7 的非优化 DB 读写，CPU 信息按型号预设返回，订货号带 SIM 标识。"
            "服务不校验 TSAP，不仿真对应 CPU 固件。"
        )

    def profile_changed(self, text):
        profile = PROFILES[text]
        self.cpu.setText(profile["cpu"])
        self.rack.setValue(profile["rack"])
        self.slot.setValue(profile["slot"])

    def build(self):
        import socket
        plc = clone(self.original)
        plc.name = self.name.text().strip()
        plc.model = self.model.currentText()
        plc.host = self.host.text().strip()
        try:
            socket.inet_pton(socket.AF_INET, plc.host)
        except OSError as exc:
            raise ValueError("请输入有效的 IPv4 地址") from exc
        plc.port = self.port.value()
        plc.rack, plc.slot = self.rack.value(), self.slot.value()
        plc.max_clients = self.clients.value()
        plc.validate()
        return plc


class DBDialog(FormDialog):
    def __init__(self, block: DataBlock, parent=None):
        super().__init__(
            "数据块配置", parent, "database",
            "定义编号、容量与非优化内存布局。",
        )
        self.original = block
        self.name = QLineEdit(block.name)
        self.name.setClearButtonEnabled(True)
        self.number = spin(1, 65535, block.number)
        self.size = spin(1, 65536, block.size, " B")

        self.row("DB 名称", self.name)
        self.row("DB 编号", self.number)
        self.row("内存容量", self.size, "变量总占用不能超过容量；修改结构前需要停止该 PLC。")
        self.note(
            "标准非优化布局：BOOL 连续按位排列；多字节类型按偶数字节对齐。"
            "地址随变量顺序自动生成。"
        )

    def build(self):
        block = clone(self.original)
        block.name = self.name.text().strip()
        if not block.name:
            raise ValueError("DB 名称不能为空")
        block.number, block.size = self.number.value(), self.size.value()
        block.build_memory()
        return block


class VariableDialog(FormDialog):
    def __init__(self, variable: Variable | None = None, parent=None):
        super().__init__(
            "编辑变量" if variable else "新增变量", parent, "sliders",
            "类型、偏移与初始值；结构修改需先停止服务。",
        )
        self.original = variable
        self.name = QLineEdit(variable.name if variable else "")
        self.name.setClearButtonEnabled(True)
        self.name.setPlaceholderText("例如 Temperature")
        self.dtype = ChoiceBox()
        self.dtype.addItems(TYPES)
        self.dtype.setCurrentText(variable.dtype if variable else "REAL")
        self.count = spin(1, 4096, variable.count if variable else 1)
        self.length = spin(1, 16382, variable.length if variable else 32)
        self.value = ValueEditor(display_value(variable.value) if variable else "0")
        self.value.configure(variable.dtype if variable else "REAL", variable.count if variable else 1)
        self.comment = QLineEdit(variable.comment if variable else "")
        self.comment.setPlaceholderText("可选，说明该变量的用途")
        self.address = QLineEdit(
            "" if variable is None or variable.offset is None
            else f"{variable.offset}.{variable.bit_offset}"
        )
        self.address.setPlaceholderText("留空自动分配，或输入 20.0 / 0.3")
        self.storage = spin(0, 65536, variable.storage_size or 0 if variable else 0, " B")
        self.storage.setSpecialValueText("按类型自动计算")
        self.storage.setToolTip("预留空间可避免后续结构变化时地址漂移。")

        self.section("标识")
        self.row("变量名", self.name)
        self.row("数据类型", self.dtype)

        self.section("存储")
        self.row("偏移地址", self.address)
        self.row("预留长度", self.storage)
        self.row("数组元素数", self.count)
        self.row("字符串长度", self.length)
        self.length_row = self.form.rowCount() - 1

        self.section("默认值")
        self.row("初始值", self.value)
        self.row("说明", self.comment)

        self.dtype.currentTextChanged.connect(self.type_changed)
        self.count.valueChanged.connect(self.reset_default)
        is_string = self.dtype.currentText() in {"STRING", "WSTRING"}
        self.length.setEnabled(is_string)
        self.form.setRowVisible(self.length_row, is_string)
        self.note(
            "先选择类型，再设置容量和初始值。偏移留空自动分配，预留长度可保持为自动。"
            "类型变更会重置该变量的模拟规则。"
        )

    def type_changed(self, dtype):
        is_string = dtype in {"STRING", "WSTRING"}
        self.length.setEnabled(is_string)
        self.form.setRowVisible(self.length_row, is_string)
        if dtype == "STRING":
            self.length.setValue(min(self.length.value(), 254))
        self.reset_default()

    def reset_default(self):
        self.value.configure(self.dtype.currentText(), self.count.value())
        self.value.setText(display_value(default_value(self.dtype.currentText(), self.count.value())))

    def build(self):
        var = clone(self.original) if self.original else Variable()
        var.name = self.name.text().strip()
        if not var.name:
            raise ValueError("变量名不能为空")
        var.dtype, var.count, var.length = self.dtype.currentText(), self.count.value(), self.length.value()
        var.value = parse_input(self.value.text(), var.dtype, var.count)
        address = self.address.text().strip()
        if address:
            parts = address.split(".")
            if len(parts) > 2:
                raise ValueError("地址格式为 字节.位，例如 20.0")
            var.offset = int(parts[0])
            var.bit_offset = int(parts[1]) if len(parts) == 2 else 0
        else:
            var.offset, var.bit_offset = None, 0
        var.storage_size = self.storage.value() or None
        var.comment = self.comment.text().strip()
        if self.original and var.dtype != self.original.dtype:
            var.simulation = Simulation()
        DataBlock(variables=[var], size=65536).build_memory()
        return var


class SimulationDialog(FormDialog):
    def __init__(self, variable: Variable, parent=None):
        super().__init__(
            f"值模拟 · {variable.name}", parent, "activity",
            "自动模拟仅在服务运行且 CPU 为 RUN 时生效。",
        )
        self.variable = variable
        sim = variable.simulation
        self.preview = QLabel()
        self.preview.setObjectName("simPreview")
        self.preview.setWordWrap(True)
        self.form.addRow(self.preview)

        self.mode = ChoiceBox()
        for key, name in MODE_NAMES.items():
            if key == "manual" or (
                variable.dtype == "BOOL" and key in {"random", "toggle"}
            ) or (
                variable.dtype in NUMERIC and key in {"random", "sine", "ramp"}
            ):
                self.mode.addItem(name, key)
        self.mode.setCurrentIndex(max(0, self.mode.findData(sim.mode)))
        self.minimum = QLineEdit(str(sim.minimum))
        self.maximum = QLineEdit(str(sim.maximum))
        self.interval = spin(50, 3_600_000, sim.interval_ms, " ms")
        self.period = spin(100, 86_400_000, sim.period_ms, " ms")

        self.section("模式")
        self.row("模拟模式", self.mode)
        bounds = QWidget()
        bounds_layout = QHBoxLayout(bounds)
        bounds_layout.setContentsMargins(0, 0, 0, 0)
        bounds_layout.setSpacing(7)
        bounds_layout.addWidget(self.minimum)
        dash = QLabel("–")
        dash.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bounds_layout.addWidget(dash)
        bounds_layout.addWidget(self.maximum)
        self.row("取值范围", bounds)
        self.bounds_row = self.form.rowCount() - 1
        self.minimum.setFixedHeight(38)
        self.maximum.setFixedHeight(38)
        self.minimum.setAccessibleName("最小值")
        self.maximum.setAccessibleName("最大值")
        self.minimum.setPlaceholderText("最小值")
        self.maximum.setPlaceholderText("最大值")

        self.section("节奏")
        self.timing_section_row = self.form.rowCount() - 1
        self.row("更新间隔", self.interval, "每次生成新值之间的时间。")
        self.interval_row = self.form.rowCount() - 1
        self.row("完整周期", self.period, "完成一轮波形所需时间，应大于更新间隔。")
        self.period_row = self.form.rowCount() - 1

        self.mode.currentIndexChanged.connect(self.update_enabled)
        self.minimum.textChanged.connect(self.update_preview)
        self.maximum.textChanged.connect(self.update_preview)
        self.interval.valueChanged.connect(self.update_preview)
        self.period.valueChanged.connect(self.update_preview)
        self.update_enabled()
        self.note(
            "模拟需要服务启动且 CPU 为 RUN。数组随机值逐项生成，波形模式同步更新全部元素。手动或客户端写入后，"
            "自动模拟将在下个更新周期覆盖该值。"
        )

    def update_enabled(self):
        mode = self.mode.currentData()
        numeric = self.variable.dtype in NUMERIC and mode != "manual"
        self.minimum.setEnabled(numeric)
        self.maximum.setEnabled(numeric)
        self.interval.setEnabled(mode != "manual")
        self.period.setEnabled(mode in {"sine", "ramp"})
        self.form.setRowVisible(self.bounds_row, numeric)
        self.form.setRowVisible(self.timing_section_row, mode != "manual")
        self.form.setRowVisible(self.interval_row, mode != "manual")
        self.form.setRowVisible(self.period_row, mode in {"sine", "ramp"})
        self.update_preview()

    def update_preview(self):
        mode = self.mode.currentData()
        interval = self.interval.value()
        if mode == "manual":
            text = "手动赋值：数值保持不变，直到手动写入或客户端写入。"
        elif self.variable.dtype == "BOOL" and mode == "random":
            text = f"每 {interval} ms 随机选择 true / false，可能连续得到相同值；需要交替变化请选择定时翻转。"
        elif mode == "toggle":
            text = f"每 {interval} ms 翻转一次 ON / OFF。"
        else:
            try:
                low = float(self.minimum.text())
                high = float(self.maximum.text())
            except ValueError:
                text = "请填写有效的数值范围。"
            else:
                if mode == "random":
                    text = f"每 {interval} ms 在 {low:g} – {high:g} 之间随机取值。"
                elif mode == "sine":
                    text = (
                        f"每 {interval} ms 采样，按 {self.period.value()} ms 周期"
                        f"在 {low:g} – {high:g} 之间正弦变化。"
                    )
                else:
                    text = (
                        f"每 {interval} ms 递增，在 {low:g} – {high:g} 之间循环，"
                        f"周期 {self.period.value()} ms。"
                    )
        self.preview.setText(text)

    def build(self):
        numeric = self.minimum.isEnabled()
        # Preserve integer precision, particularly for 64-bit variables.
        parse = int if self.variable.dtype in INT_LIMITS else float
        sim = Simulation(
            self.mode.currentData(),
            parse(self.minimum.text()) if numeric else 0,
            parse(self.maximum.text()) if numeric else 100,
            self.interval.value(),
            self.period.value(),
        )
        sim.validate(self.variable.dtype)
        return sim


class StorageDialog(FormDialog):
    def __init__(self, directory, parent=None):
        from PySide6.QtWidgets import QPushButton, QFileDialog
        super().__init__('项目保存设置', parent, 'settings', '指定新项目的默认目录，适用于 Windows 与 macOS。')
        self.directory = QLineEdit(str(directory))
        self.directory.setFixedHeight(38)
        self.directory.setMinimumWidth(180)
        browse = QPushButton('浏览…')
        browse.setFixedHeight(38)
        browse.setIcon(icons.make_icon('folder', current().text_muted, 15))
        browse.setAutoDefault(False)
        def choose():
            path = QFileDialog.getExistingDirectory(self, '默认项目保存目录', self.directory.text())
            if path:
                self.directory.setText(path)
        browse.clicked.connect(choose)
        directory_row = QWidget()
        directory_layout = QHBoxLayout(directory_row)
        directory_layout.setContentsMargins(0, 0, 0, 0)
        directory_layout.setSpacing(8)
        directory_layout.addWidget(self.directory, 1)
        directory_layout.addWidget(browse)
        self.row('默认目录', directory_row)
        self.note('仅影响新项目和首次另存为；已有项目继续保存到原文件。设置会保留到下次启动。默认使用系统文档目录下的 S7 Studio 文件夹。')

    def build(self):
        from pathlib import Path
        import tempfile
        raw = self.directory.text().strip()
        if not raw:
            raise ValueError('请选择默认保存目录')
        path = Path(raw).expanduser()
        if not path.is_absolute():
            raise ValueError('请输入绝对路径或使用选择文件夹')
        try:
            path.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryFile(dir=path):
                pass
        except OSError as exc:
            raise ValueError(f'目录不可写：{exc}') from exc
        return path
