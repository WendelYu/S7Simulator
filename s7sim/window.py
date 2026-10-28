from __future__ import annotations

import csv
import datetime as dt
import html
import time
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve, QPoint, QPropertyAnimation, QRectF, QSettings, QSize, Qt, QTimer,
)
from PySide6.QtGui import (
    QAction, QActionGroup, QColor, QFont, QFontMetrics, QKeySequence, QPainter,
    QBrush,
)
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDialog, QFileDialog, QFrame,
    QGraphicsOpacityEffect, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMainWindow, QMenu, QMessageBox, QPushButton, QScrollArea, QSpinBox, QSplitter,
    QStackedWidget, QStyle, QStyledItemDelegate, QStyleOptionViewItem,
    QTabWidget, QTableWidget, QTableWidgetItem, QTextBrowser, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from . import icons, motion, theme
from . import __version__
from .codec import NUMERIC, TYPES, default_value, display_value, make_layout, parse_input
from .dialogs import DBDialog, MODE_NAMES, PLCDialog, SimulationDialog, VariableDialog, StorageDialog
from .engine import Engine
from .value_editor import ValueEditor, BoolCombo
from .inputs import ChoiceBox, NumberBox
from .storage import default_directory, suggested_path
from .import_dialog import PointImportDialog
from .models import DataBlock, PLC, Project, Simulation, available_port, clone, demo_project
from .theme import Palette, current
from .widgets import (
    BrandMark, EmptyState, IconTile, MetricValue, NavTree, PillTabBar, SearchField,
    Sidebar, Sparkline, StatCard, StatusPill, ThemeToggle,
    Toaster, UsageBar, divider, ROLE_COUNT, ROLE_DETAIL, ROLE_ID, ROLE_KIND,
    ROLE_RUNNING, ROLE_SUBTITLE,
)

SETTINGS_ORG = "S7Simulator"
SETTINGS_APP = "S7 Studio"

MODE_COLORS = {
    "manual": "text_faint",
    "random": "info",
    "sine": "accent",
    "ramp": "warn",
    "toggle": "type_bool",
}


def label(text, name=None):
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    return widget


def button(text, handler, name=None):
    widget = QPushButton(text)
    if name:
        widget.setObjectName(name)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    widget.setAutoDefault(False)
    if handler is not None:
        widget.clicked.connect(handler)
    return widget


def mono_font(size=10.5):
    font = QFont()
    font.setFamilies(["SF Mono", "Menlo", "Cascadia Mono", "Consolas", "Liberation Mono"])
    font.setPixelSize(max(1, int(round(size * 1.333))))
    return font


def table(headers, numbered=False):
    widget = QTableWidget(0, len(headers))
    widget.setHorizontalHeaderLabels(headers)
    widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    widget.setShowGrid(False)
    widget.setAlternatingRowColors(True)
    widget.setWordWrap(False)
    widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    widget.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
    vertical = widget.verticalHeader()
    if numbered:
        vertical.show()
        vertical.setFixedWidth(34)
        vertical.setDefaultSectionSize(40)
    else:
        vertical.hide()
    horizontal = widget.horizontalHeader()
    horizontal.setHighlightSections(False)
    horizontal.setFixedHeight(38)
    horizontal.setStretchLastSection(True)
    horizontal.setSectionsMovable(True)
    horizontal.setDefaultAlignment(
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    )
    widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    return widget


def cell(text, muted=False):
    item = QTableWidgetItem(str(text))
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    if muted:
        item.setForeground(QColor(current().text_faint))
    return item


def stamp(timestamp):
    return dt.datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")


def repolish(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


class VariableDelegate(QStyledItemDelegate):
    """Editor plumbing plus the tinted data-type chip in column 1."""

    TYPE_TONES = {
        "BOOL": "type_bool",
        "BYTE": "type_int",
        "WORD": "type_int",
        "DWORD": "type_int",
        "INT": "type_int",
        "DINT": "type_int",
        "SINT": "type_int",
        "UINT": "type_int",
        "UDINT": "type_int",
        "USINT": "type_int",
        "REAL": "type_float",
        "LREAL": "type_float",
        "STRING": "type_string",
        "WSTRING": "type_string",
        "CHAR": "type_string",
        "WCHAR": "type_string",
        "TIME": "type_time",
        "DATE": "type_time",
        "TOD": "type_time",
        "DT": "type_time",
    }

    def __init__(self, window):
        super().__init__(window)
        self.window = window

    def createEditor(self, parent, option, index):
        var = self.window.db().variables[index.row()]
        if index.column() == 3 and var.dtype == "BOOL" and var.count == 1:
            return BoolCombo(parent)
        if index.column() == 1:
            editor = ChoiceBox(parent)
            editor.addItems(TYPES)
            return editor
        if index.column() == 8:
            var = self.window.db().variables[index.row()]
            if var.dtype not in {"STRING", "WSTRING"}:
                return None
            editor = NumberBox(parent)
            editor.setRange(1, 254 if var.dtype == "STRING" else 16382)
            return editor
        return super().createEditor(parent, option, index)

    def setEditorData(self, editor, index):
        var = self.window.db().variables[index.row()]
        if isinstance(editor, QComboBox):
            editor.setCurrentText(var.dtype if index.column() == 1 else index.data())
        elif isinstance(editor, QSpinBox):
            editor.setValue(var.length)
        else:
            super().setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        if isinstance(editor, QComboBox):
            model.setData(index, editor.currentText())
        elif isinstance(editor, QSpinBox):
            model.setData(index, str(editor.value()))
        else:
            super().setModelData(editor, model, index)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        super().paint(painter, option, index)
        if index.column() == 1:
            self._paint_type(painter, option, index)
        if index.column() == 0 and option.state & QStyle.StateFlag.State_Selected:
            colors = current()
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(colors.accent))
            rect = QRectF(option.rect)
            painter.drawRoundedRect(
                QRectF(rect.left() + 1.5, rect.top() + 8, 2.5, rect.height() - 16), 1.25, 1.25
            )
            painter.restore()

    def _paint_type(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        colors = current()
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        base = text.split()[-1].split("[")[0] if text else ""
        tone = QColor(getattr(colors, self.TYPE_TONES.get(base, "text_muted"), colors.text_muted))
        rect = QRectF(option.rect).adjusted(8, 0, -8, 0)
        rect.setTop(rect.center().y() - 11)
        rect.setHeight(22)
        bg = motion.lerp_color(QColor(colors.surface), tone, 0.14)
        font = QFont(option.font)
        font.setPixelSize(max(1, int(round(8.5 * 1.333))))
        font.setWeight(QFont.Weight.DemiBold)
        fm = QFontMetrics(font)
        if text.startswith("ARRAY["):
            full_label = text.split()[0]
        else:
            full_label = text
        # Show the full STRING[32] / ARRAY[4] form when it fits, otherwise fall
        # back to the type name so the chip never shows a broken bracket.
        label = full_label if fm.horizontalAdvance(full_label) <= rect.width() - 2 else base
        label = fm.elidedText(label, Qt.TextElideMode.ElideRight, max(10, int(rect.width())))
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, 6, 6)
        painter.setPen(QColor(tone))
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)
        painter.restore()


def _system_dark() -> bool:
    app = QApplication.instance()
    try:
        return app.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except AttributeError:
        return False


class MainWindow(QMainWindow):
    def __init__(self, project: Project | None = None, dark: bool | None = None,
                 theme_mode: str | None = None):
        super().__init__()
        self.project = project or demo_project()
        self.engine = Engine(self.project)
        self.path: Path | None = None
        self.dark_theme = bool(dark)
        self.theme_mode = theme_mode or ("dark" if dark else "light")
        self.dirty = False
        self.plc_id: str | None = None
        self.db_id: str | None = None
        self.selected_var_id: str | None = None
        self.building_table = False
        self.value_flashes: dict[tuple[str, int], float] = {}
        self.log_signature = None
        self.connection_signature = None
        self._icon_specs: dict[QPushButton, list[str]] = {}
        self._theme_overlay: QLabel | None = None
        self._theme_anim: QPropertyAnimation | None = None
        self._footer_tone: str | None = None
        self._sim_active: bool | None = None
        self.settings = QSettings(SETTINGS_ORG, SETTINGS_APP)

        self.setWindowTitle("S7 Studio · PLC Simulator")
        self.resize(1600, 1000)
        self.setMinimumSize(1160, 780)
        self.colors = theme.apply_theme(QApplication.instance(), self.dark_theme)
        self._build_menu()
        self._build_ui()
        try:
            self._system_hints = QApplication.instance().styleHints()
            self._system_hints.colorSchemeChanged.connect(self._system_scheme_changed)
        except AttributeError:
            self._system_hints = None
        self.toaster = Toaster(self)
        self.rebuild_tree()
        self.update_title()
        self._sync_theme(self.colors, animate=False)
        self.refresh()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(250)

    # ------------------------------------------------------------------
    # construction helpers

    def _icon_button(self, handler, icon_name, tooltip, role="muted", size=32):
        widget = QPushButton("")
        widget.setObjectName("iconButton")
        widget.setFixedSize(size, size)
        widget.setIconSize(QSize(16, 16))
        widget.setCursor(Qt.CursorShape.PointingHandCursor)
        widget.setToolTip(tooltip)
        widget.setAccessibleName(tooltip)
        widget.setAutoDefault(False)
        widget.clicked.connect(handler)
        self._icon_specs[widget] = [icon_name, role]
        return widget

    def _text_button(self, text, handler, icon_name, role="muted", name=None, tooltip=None):
        widget = button(text, handler, name)
        widget.setIconSize(QSize(15, 15))
        if tooltip:
            widget.setToolTip(tooltip)
        self._icon_specs[widget] = [icon_name, role]
        return widget

    def _build_menu(self):
        bar = self.menuBar()

        def add(menu, text, handler, shortcut=None):
            action = QAction(text, self)
            if shortcut is not None:
                action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(handler)
            menu.addAction(action)
            return action

        file_menu = bar.addMenu("文件")
        add(file_menu, "新建项目", self.new_project, QKeySequence.StandardKey.New)
        add(file_menu, "打开项目…", self.open_project, QKeySequence.StandardKey.Open)
        add(file_menu, "保存项目", self.save_project, QKeySequence.StandardKey.Save)
        add(file_menu, "项目另存为…", self.save_as, QKeySequence.StandardKey.SaveAs)
        add(file_menu, "项目保存设置…", self.storage_settings)
        file_menu.addSeparator()
        add(file_menu, "加载示例项目", self.load_demo)
        add(file_menu, "批量导入点位…", self.import_points)
        add(file_menu, "导出当前 DB 定义…", self.export_db)
        add(file_menu, "导出事件日志…", self.export_logs)
        file_menu.addSeparator()
        add(file_menu, "退出", self.close, QKeySequence.StandardKey.Quit)

        plc_menu = bar.addMenu("PLC")
        add(plc_menu, "新增 PLC", self.add_plc)
        add(plc_menu, "编辑当前 PLC", self.edit_plc)
        add(plc_menu, "删除当前 PLC", self.delete_plc)
        plc_menu.addSeparator()
        add(plc_menu, "启动全部", self.start_all)
        add(plc_menu, "停止全部", self.stop_all)

        db_menu = bar.addMenu("数据块")
        add(db_menu, "新增 DB", self.add_db)
        add(db_menu, "编辑当前 DB", self.edit_db)
        add(db_menu, "复制当前 DB", self.duplicate_db)
        add(db_menu, "删除当前 DB", self.delete_db)

        view_menu = bar.addMenu("外观")
        self.theme_group = QActionGroup(self)
        self.theme_group.setExclusive(True)
        self.auto_action = QAction("跟随系统", self)
        self.auto_action.setCheckable(True)
        self.auto_action.triggered.connect(lambda: self.set_theme_mode("auto"))
        self.theme_group.addAction(self.auto_action)
        self.light_action = QAction("浅色主题", self)
        self.light_action.setCheckable(True)
        self.light_action.triggered.connect(lambda: self.set_theme(False))
        self.theme_group.addAction(self.light_action)
        self.dark_action = QAction("深色主题", self)
        self.dark_action.setCheckable(True)
        self.dark_action.triggered.connect(lambda: self.set_theme(True))
        self.theme_group.addAction(self.dark_action)
        view_menu.addAction(self.auto_action)
        view_menu.addAction(self.light_action)
        view_menu.addAction(self.dark_action)
        view_menu.addSeparator()
        self.motion_action = QAction("启用界面动效", self)
        self.motion_action.setCheckable(True)
        self.motion_action.setChecked(motion.enabled())
        self.motion_action.triggered.connect(self._toggle_motion)
        view_menu.addAction(self.motion_action)

        help_menu = bar.addMenu("帮助")
        add(help_menu, "连接示例与功能范围", self.show_help)
        add(help_menu, "复制连接示例", self.copy_client_example)

    def set_theme_mode(self, mode):
        """Apply light, dark, or follow the OS appearance and persist the mode."""
        app = QApplication.instance()
        if app is None:
            return
        if mode not in {"auto", "light", "dark"}:
            mode = "light"
        dark = _system_dark() if mode == "auto" else mode == "dark"
        self.set_theme(dark, persist=False, mode=mode)
        self.settings.setValue("ui/theme", mode)

    def _system_scheme_changed(self, _scheme):
        if self.theme_mode == "auto":
            self.set_theme(_system_dark(), persist=False, mode="auto")

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("appRoot")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setSpacing(0)
        outer.setContentsMargins(0, 0, 0, 0)

        self.sidebar = Sidebar()
        self.sidebar.setFixedWidth(244)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(18, 22, 18, 16)
        side.setSpacing(0)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(11)
        self.brand = BrandMark(38)
        brand_row.addWidget(self.brand)
        brand_titles = QVBoxLayout()
        brand_titles.setSpacing(0)
        brand_titles.addWidget(label("S7 STUDIO", "brandTitle"))
        brand_titles.addWidget(label("PLC SIMULATOR", "brandSub"))
        brand_row.addLayout(brand_titles)
        brand_row.addStretch(1)
        side.addLayout(brand_row)

        side.addSpacing(28)
        workspace_row = QHBoxLayout()
        workspace_row.addWidget(label("工作空间", "sideLabel"))
        workspace_row.addStretch(1)
        self.workspace_count = label("", "sideCount")
        workspace_row.addWidget(self.workspace_count)
        side.addLayout(workspace_row)
        side.addSpacing(8)

        self.tree = NavTree()
        self.tree.currentItemChanged.connect(self.tree_selected)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_tree_menu)
        self.tree.setToolTip("右键 PLC 或 DB 可配置、复制或删除；Delete 删除所选节点")
        delete_node = QAction(self.tree)
        delete_node.setShortcut(QKeySequence.StandardKey.Delete)
        delete_node.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        delete_node.triggered.connect(self.delete_tree_node)
        self.tree.addAction(delete_node)
        side.addWidget(self.tree, 1)
        side.addSpacing(10)
        self.add_plc_button = self._text_button(
            "新增 PLC", self.add_plc, "plus", role="sidebar", name="sidebarButton",
            tooltip="创建一台新的 S7 PLC 模拟实例",
        )
        side.addWidget(self.add_plc_button)
        side.addSpacing(16)
        side.addWidget(divider(object_name="sideDivider"))
        side.addSpacing(12)
        side.addWidget(label("S7 TCP  ·  标准非优化 DB", "sideFoot"))
        side.addWidget(label(f"macOS / Windows   ·   v{__version__}", "sideFoot"))
        outer.addWidget(self.sidebar)

        content = QWidget()
        content.setObjectName("content")
        body = QVBoxLayout(content)
        body.setContentsMargins(24, 16, 24, 10)
        body.setSpacing(14)
        outer.addWidget(content, 1)

        top = QHBoxLayout()
        top.setSpacing(9)
        self.breadcrumb = label("工作空间", "breadcrumb")
        top.addWidget(self.breadcrumb, 1)
        self.project_label = label("未保存的项目", "projectChip")
        self.project_label.setMaximumWidth(260)
        top.addWidget(self.project_label)
        top.addSpacing(4)
        self.theme_toggle = ThemeToggle()
        self.theme_toggle.toggled.connect(self.set_theme)
        top.addWidget(self.theme_toggle)
        self.open_button = self._icon_button(self.open_project, "folder", "打开项目")
        self.save_button = self._icon_button(self.save_project, "save", "保存项目")
        top.addWidget(self.open_button)
        top.addWidget(self.save_button)
        body.addLayout(top)

        heading = QHBoxLayout()
        heading.setSpacing(8)
        titles = QVBoxLayout()
        titles.setSpacing(5)
        self.title = label("数据块工作台", "pageTitle")
        self.subtitle = label("创建、观察并模拟你的 PLC 数据。", "subtitle")
        titles.addWidget(self.title)
        titles.addWidget(self.subtitle)
        heading.addLayout(titles, 1)
        self.state_pill = StatusPill()
        heading.addWidget(self.state_pill, 0, Qt.AlignmentFlag.AlignVCenter)
        heading.addSpacing(6)
        self.config_button = self._text_button(
            "PLC 配置", self.edit_plc, "settings", role="muted",
            tooltip="编辑当前 PLC 的连接配置（需先停止服务）",
        )
        self.cpu_button = self._text_button(
            "CPU RUN", self.toggle_cpu, "power", role="muted",
            tooltip="切换 CPU RUN/STOP；TCP 服务保持监听，STOP 时暂停值模拟",
        )
        self.run_button = self._text_button(
            "启动服务", self.toggle_server, "play", role="on_accent", name="primary",
            tooltip="启动或停止当前 PLC 的 S7 服务",
        )
        heading.addWidget(self.config_button)
        heading.addWidget(self.cpu_button)
        heading.addWidget(self.run_button)
        body.addLayout(heading)

        cards = QHBoxLayout()
        cards.setSpacing(12)
        self.status_card = StatCard("PLC 状态", "OFFLINE", "服务尚未启动", "activity", "muted")
        self.connection_card = StatCard("活跃连接", "0", "最大 32 个连接", "link", "info")
        self.db_card = StatCard("数据块 / 变量", "0 / 0", "已配置的 DB 与变量", "database", "accent")
        self.io_card = StatCard("读 / 写操作", "0 / 0", "本次应用会话累计", "terminal", "muted")
        for card in [self.status_card, self.connection_card, self.db_card, self.io_card]:
            cards.addWidget(card, 1)
        body.addLayout(cards)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabbar = PillTabBar()
        self.tabs.setTabBar(self.tabbar)
        self.tabs.addTab(self._build_db_page(), "数据块")
        self.tabs.addTab(self._build_connections_page(), "连接监控")
        self.tabs.addTab(self._build_logs_page(), "事件日志")
        self.tabs.currentChanged.connect(self._tab_changed)
        body.addWidget(self.tabs, 1)

        footer = QHBoxLayout()
        footer.setSpacing(7)
        self.footer_dot = label("●")
        self.footer_dot.setStyleSheet(f"color: {self.colors.text_faint}; font-size: 9px;")
        footer.addWidget(self.footer_dot, 0, Qt.AlignmentFlag.AlignVCenter)
        self.footer = label("本地模拟环境  ·  所有数值均为模拟数据", "muted")
        footer.addWidget(self.footer, 1)
        self.footer_right = label("本地模拟", "muted")
        footer.addWidget(self.footer_right)
        body.addLayout(footer)

        self.statusBar().setSizeGripEnabled(False)
        self.statusBar().showMessage("就绪  ·  选择数据块，双击监控值即可写入")

    def _build_db_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 14, 0, 0)
        layout.setSpacing(12)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.db_heading = label("DB1 · Process_Data", "sectionTitle")
        toolbar.addWidget(self.db_heading)
        toolbar.addStretch(1)
        self.search = SearchField("搜索变量、类型、地址…")
        self.search.setFixedWidth(250)
        self.search.textChanged.connect(self.filter_table)
        toolbar.addWidget(self.search)
        self.add_db_button = self._text_button("新建 DB", self.add_db, "plus", role="muted")
        self.edit_db_button = self._text_button("编辑 DB", self.edit_db, "edit", role="muted")
        self.add_var_button = self._text_button(
            "新增变量", self.add_variable, "plus", role="on_accent", name="primary"
        )
        toolbar.addWidget(self.add_db_button)
        toolbar.addWidget(self.edit_db_button)
        toolbar.addWidget(self.add_var_button)
        self.import_points_button = self._text_button("导入点位", self.import_points, "plus", role="muted")
        toolbar.addWidget(self.import_points_button)
        layout.addLayout(toolbar)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(8)

        self.data_panel = QFrame()
        self.data_panel.setObjectName("panel")
        data_layout = QVBoxLayout(self.data_panel)
        data_layout.setContentsMargins(10, 10, 10, 9)
        data_layout.setSpacing(8)

        self.data_table = table(
            ["名称", "数据类型", "偏移地址", "监控值", "值模拟", "注释", "长度 / B", "配置值", "容量"],
            numbered=True,
        )
        self.data_table.horizontalHeaderItem(8).setToolTip("String / WString 的最大字符容量")
        self.data_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.data_table.setItemDelegate(VariableDelegate(self))
        self.data_table.currentCellChanged.connect(self.variable_selected)
        self.data_table.itemChanged.connect(self.value_edited)
        header = self.data_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        for index, width in enumerate([134, 84, 76, 100, 84, 0, 72, 84, 50]):
            if width:
                self.data_table.setColumnWidth(index, width)
        self.data_table.setColumnWidth(5, 132)

        self.data_empty = EmptyState()
        self.data_stack = QStackedWidget()
        self.data_stack.addWidget(self.data_table)
        self.data_stack.addWidget(self.data_empty)
        data_layout.addWidget(self.data_stack, 1)

        table_footer = QVBoxLayout()
        table_footer.setSpacing(3)
        memory_row = QHBoxLayout()
        memory_row.setSpacing(8)
        self.memory_label = label("", "memoryLabel")
        memory_row.addWidget(self.memory_label)
        self.usage_bar = UsageBar()
        memory_row.addWidget(self.usage_bar)
        self.usage_text = label("", "memoryLabel")
        memory_row.addWidget(self.usage_text)
        memory_row.addStretch(1)
        table_footer.addLayout(memory_row)
        self.table_hint = label("双击监控值写入  ·  双击地址 / 长度编辑结构", "memoryLabel")
        table_footer.addWidget(self.table_hint)
        data_layout.addLayout(table_footer)
        split.addWidget(self.data_panel)

        self.inspector = QFrame()
        self.inspector.setObjectName("panel")
        inspector = QVBoxLayout(self.inspector)
        inspector.setContentsMargins(16, 12, 16, 10)
        inspector.setSpacing(7)

        inspector_head = QHBoxLayout()
        inspector_head.setSpacing(8)
        inspector_head.addWidget(label("变量检查器", "sectionTitle"))
        inspector_head.addStretch(1)
        self.var_live = label("实时", "countBadge")
        self.var_live.hide()
        inspector_head.addWidget(self.var_live)
        inspector.addLayout(inspector_head)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        inner = QWidget()
        inner.setObjectName("inspectorInner")
        detail = QVBoxLayout(inner)
        detail.setContentsMargins(0, 0, 0, 0)
        detail.setSpacing(5)

        self.var_name = label("选择一个变量", "varName")
        self.var_name.setWordWrap(True)
        detail.addWidget(self.var_name)
        self.var_meta = label("添加变量后可在此修改数值与模拟规则", "varMeta")
        self.var_meta.setWordWrap(True)
        detail.addWidget(self.var_meta)

        value_box = QFrame()
        value_box.setObjectName("valueBox")
        value_layout = QVBoxLayout(value_box)
        value_layout.setContentsMargins(13, 8, 13, 8)
        value_layout.setSpacing(5)
        value_head = QHBoxLayout()
        value_head.setSpacing(6)
        value_head.addWidget(label("当前值", "fieldHint"))
        value_head.addStretch(1)
        self.copy_button = self._icon_button(self.copy_value, "copy", "复制当前值", size=24)
        value_head.addWidget(self.copy_button)
        value_layout.addLayout(value_head)
        self.var_value = MetricValue()
        value_layout.addWidget(self.var_value)
        input_row = QHBoxLayout()
        input_row.setSpacing(7)
        self.value_input = ValueEditor()
        self.value_input.setObjectName("valueInput")
        self.value_input.setPlaceholderText("输入新值，回车写入…")
        self.value_input.setFixedHeight(38)
        self.value_input.returnPressed.connect(self.write_selected_value)
        input_row.addWidget(self.value_input, 1)
        self.write_button = self._text_button(
            "写入", self.write_selected_value, "check", role="on_accent", name="compactPrimary"
        )
        self.write_button.setFixedHeight(38)
        input_row.addWidget(self.write_button)
        value_layout.addLayout(input_row)
        detail.addWidget(value_box)

        self.sim_start_button = self._text_button('启动服务并模拟', self.start_simulation, 'play', role='on_accent', name='compactPrimary')
        self.sim_start_button.hide()
        detail.addWidget(self.sim_start_button)
        sim_row = QHBoxLayout()
        sim_row.setSpacing(8)
        sim_col = QVBoxLayout()
        sim_col.setSpacing(1)
        sim_col.addWidget(label("值模拟", "fieldHint"))
        self.sim_summary = label("手动赋值", "simSummary")
        self.sim_summary.setWordWrap(True)
        sim_col.addWidget(self.sim_summary)
        sim_row.addLayout(sim_col, 1)
        self.sim_button = self._text_button(
            "配置", self.configure_simulation, "sliders", role="accent", name="softButton",
            tooltip="配置随机、正弦、斜坡或定时翻转",
        )
        self.sim_button.setObjectName("smallSoftButton")
        sim_row.addWidget(self.sim_button, 0, Qt.AlignmentFlag.AlignBottom)
        detail.addLayout(sim_row)

        self.sparkline = Sparkline()
        self.sparkline.setFixedHeight(110)
        detail.addWidget(self.sparkline)
        detail.addStretch(1)
        scroll.setWidget(inner)
        inspector.addWidget(scroll, 1)

        inspector.addWidget(divider())
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.edit_var_button = self._text_button(
            "编辑变量", self.edit_variable, "edit", role="accent", name="softButton"
        )
        self.delete_var_button = self._text_button(
            "删除", self.delete_variable, "trash", role="danger", name="danger"
        )
        actions.addWidget(self.edit_var_button, 1)
        actions.addWidget(self.delete_var_button)
        inspector.addLayout(actions)

        self.inspector.setMinimumWidth(298)
        self.inspector.setMaximumWidth(320)
        split.addWidget(self.inspector)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 0)
        split.setSizes([930, 310])
        self.db_splitter = split
        layout.addWidget(split, 1)
        return page

    def _build_connections_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 14, 0, 0)
        layout.setSpacing(12)

        head = QHBoxLayout()
        head.setSpacing(10)
        titles = QVBoxLayout()
        titles.setSpacing(4)
        titles.addWidget(label("客户端会话", "sectionTitle"))
        titles.addWidget(label("显示当前 PLC 的活跃连接及最近断开的会话，每个 TCP 连接单独计数。", "subtitle"))
        head.addLayout(titles, 1)
        self.copy_example_button = self._text_button(
            "复制连接示例", self.copy_client_example, "link", role="accent", name="softButton"
        )
        head.addWidget(self.copy_example_button)
        layout.addLayout(head)

        self.conn_summary = label("活跃 0    ·    累计读 0    ·    累计写 0", "memoryLabel")
        layout.addWidget(self.conn_summary)

        panel = QFrame()
        panel.setObjectName("panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(10, 10, 10, 10)
        panel_layout.setSpacing(0)
        self.connection_table = table(
            ["客户端 IP", "端口", "状态", "连接时间", "持续时间", "读次数", "写次数", "读 / 写字节"]
        )
        self.connection_table.setColumnWidth(0, 150)
        self.connection_table.setColumnWidth(1, 70)
        self.connection_table.setColumnWidth(2, 92)
        self.connection_table.setColumnWidth(3, 96)
        self.connection_table.setColumnWidth(4, 100)
        self.connection_table.setColumnWidth(5, 80)
        self.connection_table.setColumnWidth(6, 80)
        self.connection_empty = EmptyState()
        self.connection_empty.set_content(
            "link",
            "尚无客户端连接",
            "启动 S7 服务后，用下方的 Python 示例或任意 S7 客户端连接，会话会实时出现在这里。",
            "复制连接示例",
            self.copy_client_example,
            "copy",
        )
        self.connection_stack = QStackedWidget()
        self.connection_stack.addWidget(self.connection_table)
        self.connection_stack.addWidget(self.connection_empty)
        panel_layout.addWidget(self.connection_stack)
        layout.addWidget(panel, 1)
        return page

    def _build_logs_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 14, 0, 0)
        layout.setSpacing(12)

        head = QHBoxLayout()
        head.setSpacing(10)
        titles = QVBoxLayout()
        titles.setSpacing(4)
        titles.addWidget(label("S7 服务事件", "sectionTitle"))
        titles.addWidget(label("显示最近 300 条事件；模拟更新不逐条记录。", "subtitle"))
        head.addLayout(titles, 1)
        self.export_logs_button = self._text_button(
            "导出 CSV", self.export_logs, "download", role="muted"
        )
        self.clear_logs_button = self._text_button(
            "清空日志", self.clear_logs, "trash", role="danger", name="danger"
        )
        head.addWidget(self.export_logs_button)
        head.addWidget(self.clear_logs_button)
        layout.addLayout(head)

        panel = QFrame()
        panel.setObjectName("panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(10, 10, 10, 10)
        panel_layout.setSpacing(0)
        self.log_table = table(["时间", "事件", "客户端", "详情"])
        self.log_table.setColumnWidth(0, 92)
        self.log_table.setColumnWidth(1, 100)
        self.log_table.setColumnWidth(2, 180)
        self.log_empty = EmptyState()
        self.log_empty.set_content(
            "terminal",
            "还没有事件",
            "启动服务或连接客户端后，启动、读写、CPU 切换和错误都会实时出现在这里。",
        )
        self.log_stack = QStackedWidget()
        self.log_stack.addWidget(self.log_table)
        self.log_stack.addWidget(self.log_empty)
        panel_layout.addWidget(self.log_stack)
        layout.addWidget(panel, 1)
        return page

    # ------------------------------------------------------------------
    # theme

    def set_theme(self, dark, persist=True, animate=True, mode=None):
        dark = bool(dark)
        self.theme_mode = mode or ("dark" if dark else "light")
        app = QApplication.instance()
        if app is None:
            return
        if self._theme_anim is not None:
            self._theme_anim.stop()
            self._theme_anim.deleteLater()
            self._theme_anim = None
        if self._theme_overlay is not None:
            self._theme_overlay.hide()
            self._theme_overlay.deleteLater()
            self._theme_overlay = None
        overlay = None
        if (
            animate
            and motion.enabled()
            and self.isVisible()
            and app.platformName() != "offscreen"
            and self.dark_theme != dark
        ):
            try:
                overlay = QLabel(self)
                overlay.setPixmap(self.grab())
                overlay.setGeometry(self.rect())
                overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                effect = QGraphicsOpacityEffect(overlay)
                effect.setOpacity(1.0)
                overlay.setGraphicsEffect(effect)
                overlay.show()
                overlay.raise_()
                self._theme_overlay = overlay
            except Exception:
                overlay = None

        self.dark_theme = dark
        colors = theme.apply_theme(app, dark)
        self.colors = colors
        self._sync_theme(colors, animate=animate)
        if persist:
            self.settings.setValue("ui/theme", self.theme_mode)
        self.refresh()

        if overlay is not None:
            anim = QPropertyAnimation(overlay.graphicsEffect(), b"opacity", self)
            anim.setDuration(280)
            anim.setStartValue(1.0)
            anim.setEndValue(0.0)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)

            def done():
                overlay.deleteLater()
                anim.deleteLater()
                self._theme_overlay = None
                self._theme_anim = None

            anim.finished.connect(done)
            anim.start()
            self._theme_anim = anim

    def _toggle_motion(self, enabled):
        motion.set_enabled(bool(enabled))
        self.tree.setAnimated(bool(enabled))
        self.connection_signature = self.log_signature = None
        self.settings.setValue("ui/motion", bool(enabled))
        self.refresh()
        self.notify("已启用界面动效" if enabled else "已关闭界面动效", "info")

    def _sync_theme(self, colors: Palette, animate=False):
        self.colors = colors
        self.sidebar.apply_theme(colors)
        self.brand.apply_theme(colors)
        self.theme_toggle.apply_theme(colors)
        self.theme_toggle.set_dark(self.dark_theme, animate=animate)
        self.tree.apply_theme(colors)
        self.tabbar.apply_theme(colors)
        self.search.apply_theme(colors)
        self.state_pill.apply_theme(colors)
        for card in [self.status_card, self.connection_card, self.db_card, self.io_card]:
            card.apply_theme(colors)
        self.sparkline.apply_theme(colors)
        self.var_value.apply_theme(colors)
        self.usage_bar.apply_theme(colors)
        self.data_empty.apply_theme(colors)
        self.connection_empty.apply_theme(colors)
        self.log_empty.apply_theme(colors)
        self.toaster.apply_theme(colors)
        self.auto_action.setChecked(self.theme_mode == "auto")
        self.light_action.setChecked(self.theme_mode == "light")
        self.dark_action.setChecked(self.theme_mode == "dark")
        self.motion_action.setChecked(motion.enabled())
        self._apply_icons()
        self._apply_table_colors()
        self.connection_signature = None
        self.log_signature = None
        self._footer_tone = None
        self.tree.viewport().update()
        self.data_table.viewport().update()

    def _icon_color(self, role):
        c = self.colors
        return {
            "on_accent": c.on_accent,
            "accent": c.accent,
            "danger": c.danger,
            "sidebar": c.sidebar_text,
            "muted": c.text_muted,
        }.get(role, c.text_muted)

    def _apply_icons(self):
        for widget, spec in list(self._icon_specs.items()):
            try:
                name, role = spec
                widget.setIcon(icons.make_icon(name, self._icon_color(role), 16))
            except RuntimeError:
                self._icon_specs.pop(widget, None)

    def _apply_table_colors(self):
        colors = self.colors
        db = self.db()
        self.data_table.blockSignals(True)
        for row in range(self.data_table.rowCount()):
            for col in (2,):
                item = self.data_table.item(row, col)
                if item:
                    item.setForeground(QColor(colors.text_faint))
            item = self.data_table.item(row, 5)
            if item:
                item.setForeground(QColor(colors.text_muted))
            item = self.data_table.item(row, 3)
            if item:
                item.setForeground(QColor(colors.accent))
            item = self.data_table.item(row, 4)
            if item:
                mode = db.variables[row].simulation.mode if db and row < len(db.variables) else "manual"
                item.setForeground(QColor(getattr(colors, MODE_COLORS.get(mode, "text_faint"))))
            for col in (6, 7, 8):
                item = self.data_table.item(row, col)
                if item:
                    item.setForeground(QColor(colors.text_muted))
        self.data_table.blockSignals(False)
        self.data_table.viewport().update()

    # ------------------------------------------------------------------
    # project selection

    def plc(self):
        return next((p for p in self.project.plcs if p.id == self.plc_id), None)

    def db(self):
        plc = self.plc()
        return next((db for db in plc.blocks if db.id == self.db_id), None) if plc else None

    def variable_index(self):
        db = self.db()
        return (
            next((i for i, var in enumerate(db.variables) if var.id == self.selected_var_id), None)
            if db
            else None
        )

    def mark_dirty(self):
        self.dirty = True
        self.update_title()

    def update_title(self):
        name = self.path.name if self.path else self.project.name
        self.setWindowTitle(f"{name}[*] — S7 Studio")
        self.setWindowModified(self.dirty)
        chip = self.path.name if self.path else "未保存的项目"
        self.project_label.setText(chip)
        self.project_label.setToolTip(str(self.path) if self.path else "项目尚未保存")
        dirty = "true" if self.dirty else "false"
        if self.project_label.property("dirty") != dirty:
            self.project_label.setProperty("dirty", dirty)
            repolish(self.project_label)

    def error(self, exc):
        QMessageBox.warning(self, "操作未完成", str(exc))

    def notify(self, text, kind="success"):
        toaster = getattr(self, "toaster", None)
        if toaster is not None:
            toaster.show(str(text), kind)

    def rebuild_tree(self):
        self.tree.snap_selection()
        self.tree.blockSignals(True)
        self.tree.clear()
        selected = None
        db_count = 0
        for plc in self.project.plcs:
            runtime = self.engine.runtime(plc)
            item = QTreeWidgetItem([plc.name])
            item.setData(0, ROLE_ID, (plc.id, None))
            item.setData(0, ROLE_KIND, "plc")
            item.setData(0, ROLE_RUNNING, bool(runtime.running))
            item.setData(0, ROLE_SUBTITLE, f"{plc.model} · :{plc.port}")
            item.setToolTip(0, f"{plc.name}\n{plc.model} · {plc.host}:{plc.port}")
            self.tree.addTopLevelItem(item)
            if plc.id == self.plc_id:
                selected = item
            for block in plc.blocks:
                db_count += 1
                child = QTreeWidgetItem([f"DB{block.number}  {block.name}"])
                child.setData(0, ROLE_ID, (plc.id, block.id))
                child.setData(0, ROLE_KIND, "db")
                child.setData(0, ROLE_SUBTITLE, f"DB{block.number}")
                child.setData(0, ROLE_DETAIL, block.name)
                child.setData(0, ROLE_COUNT, len(block.variables))
                child.setToolTip(0, f"DB{block.number} · {block.name}\n{len(block.variables)} 个变量 · {block.size} B")
                item.addChild(child)
                if block.id == self.db_id and plc.id == self.plc_id:
                    selected = child
            item.setExpanded(True)
        if selected is None and self.tree.topLevelItemCount():
            item = self.tree.topLevelItem(0)
            selected = item.child(0) if item.childCount() else item
        self.tree.setCurrentItem(selected)
        self.tree.blockSignals(False)
        self.tree.snap_selection()
        self.workspace_count.setText(
            f"{len(self.project.plcs)} PLC · {db_count} DB" if self.project.plcs else "空工作空间"
        )
        self.tree_selected(selected, None)

    def tree_selected(self, item, previous):
        previous_ids = self.plc_id, self.db_id
        if item:
            ids = item.data(0, ROLE_ID)
            if not ids:
                return
            self.plc_id, self.db_id = ids
            if self.db_id is None:
                plc = self.plc()
                self.db_id = plc.blocks[0].id if plc and plc.blocks else None
        else:
            self.plc_id = self.db_id = None
        self.log_signature = self.connection_signature = None
        if previous_ids != (self.plc_id, self.db_id):
            self.selected_var_id = None
        self.populate_table()
        self.refresh()

    def run_tree_action(self, ids, callback):
        # Resolve IDs afresh: refreshes and edits can replace the tree items.
        for i in range(self.tree.topLevelItemCount()):
            root = self.tree.topLevelItem(i)
            for item in [root, *(root.child(j) for j in range(root.childCount()))]:
                if item.data(0, ROLE_ID) == ids:
                    self.tree.setCurrentItem(item)
                    self.tree_selected(item, None)
                    callback()
                    return

    def tree_menu(self, item):
        menu = QMenu(self)
        menu.setMinimumWidth(224)
        menu.setToolTipsVisible(True)
        ids = item.data(0, ROLE_ID) if item else None
        if ids:
            self.tree.setCurrentItem(item)
            plc = next((p for p in self.project.plcs if p.id == ids[0]), None)
            if plc is None:
                return menu
            running = self.engine.runtime(plc).running
            heading = menu.addAction(item.text(0))
            heading.setEnabled(False)
            menu.addSeparator()

            def action(text, icon, callback, structural=False, danger=False):
                entry = menu.addAction(icons.make_icon(icon, current().danger if danger else current().text_muted, 16), text)
                entry.setIconVisibleInMenu(True)
                entry.setEnabled(not (structural and running))
                if structural and running:
                    entry.setToolTip("请先停止该 PLC 的服务，再修改结构")
                entry.triggered.connect(lambda checked=False: self.run_tree_action(ids, callback))
                return entry

            if ids[1] is None:
                action("停止服务" if running else "启动服务", "stop" if running else "play", self.toggle_server)
                action("PLC 配置…", "settings", self.edit_plc, structural=True)
                menu.addSeparator()
                action("新建 DB…", "plus", self.add_db, structural=True)
                action("导入点位…", "download", self.import_points, structural=True)
                menu.addSeparator()
                action("停止并删除 PLC…" if running else "删除 PLC…", "trash", self.delete_plc, danger=True)
            else:
                action("DB 配置…", "settings", self.edit_db, structural=True)
                action("新增变量…", "plus", self.add_variable, structural=True)
                action("复制 DB", "copy", self.duplicate_db, structural=True)
                menu.addSeparator()
                action("删除 DB…", "trash", self.delete_db, structural=True, danger=True)
            if running:
                menu.addSeparator()
                hint = menu.addAction("服务运行中 · 停止后可修改结构")
                hint.setEnabled(False)
        else:
            entry = menu.addAction(icons.make_icon("plus", current().text_muted, 16), "新增 PLC…")
            entry.triggered.connect(self.add_plc)
        return menu

    def show_tree_menu(self, position):
        item = self.tree.itemAt(position)
        menu = self.tree_menu(item)
        menu.aboutToHide.connect(menu.deleteLater)
        menu.popup(self.tree.viewport().mapToGlobal(position))
        motion.fade_window(menu, 100)

    def delete_tree_node(self):
        item = self.tree.currentItem()
        if item is not None:
            ids = item.data(0, ROLE_ID)
            if ids:
                self.run_tree_action(ids, self.delete_db if ids[1] else self.delete_plc)

    def _tab_changed(self, index):
        titles = ("数据块工作台", "连接监控", "事件日志")
        self.title.setText(titles[index] if 0 <= index < len(titles) else "工作台")
        self.refresh()

        if self.isVisible():
            motion.fade_in(self.tabs.widget(index), 140, low=0.8)

    # ------------------------------------------------------------------
    # table

    def populate_table(self):
        self.building_table = True
        self.data_table.blockSignals(True)
        db, plc = self.db(), self.plc()
        self.data_table.setRowCount(len(db.variables) if db else 0)
        if db:
            layouts, used = make_layout(db.variables, db.size)
            for row, (var, entry) in enumerate(zip(db.variables, layouts)):
                dtype = var.dtype
                if dtype in {"STRING", "WSTRING"}:
                    dtype += f"[{var.length}]"
                if var.count > 1:
                    dtype = f"ARRAY[{var.count}] {dtype}"
                capacity = (
                    str(var.length)
                    if var.dtype in {"STRING", "WSTRING"}
                    else "—"
                )
                storage = var.storage_size or (
                    (var.count + 7) // 8 if var.dtype == "BOOL" else entry.size * var.count
                )
                values = [
                    var.name,
                    dtype,
                    f"{entry.offset}.{entry.bit}",
                    display_value(var.value),
                    MODE_NAMES[var.simulation.mode],
                    var.comment,
                    str(storage),
                    display_value(var.value),
                    capacity,
                ]
                for col, text in enumerate(values):
                    item = cell(text, col == 2)
                    item.setToolTip(text)
                    if col == 5:
                        item.setForeground(QColor(self.colors.text_muted))
                    if col in {1, 2, 6} or (col == 8 and var.dtype in {"STRING", "WSTRING"}):
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                        item.setToolTip("停止服务后双击编辑；偏移留空恢复自动，长度 0 恢复按类型计算")
                    if col == 3:
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                        item.setForeground(QColor(self.colors.accent))
                        item.setFont(mono_font(10.5))
                        item.setToolTip("双击写入监控值")
                    if col == 4:
                        item.setForeground(
                            QColor(getattr(self.colors, MODE_COLORS.get(var.simulation.mode, "text_faint")))
                        )
                    if col == 7:
                        item.setForeground(QColor(self.colors.text_muted))
                    self.data_table.setItem(row, col, item)
            pct = int(round(used / db.size * 100)) if db.size else 0
            self.memory_label.setText(
                f"已使用 {used} / {db.size} B    ·    {len(db.variables)} 个变量    ·    DB{db.number}"
            )
            self.usage_text.setText(f"{pct}%")
            self.usage_bar.set_usage(used, db.size)
            self.db_heading.setText(f"DB{db.number}  ·  {db.name}")
            self.search.setEnabled(True)
            if db.variables:
                self.data_stack.setCurrentWidget(self.data_table)
            else:
                self.data_empty.set_content(
                    "sliders", "这个数据块还没有变量",
                    "添加变量后可在此实时监控数值、写入新值并配置模拟规则。",
                    "新增变量", self.add_variable, "plus",
                )
                self.data_stack.setCurrentWidget(self.data_empty)
        else:
            self.memory_label.setText("新建数据块后即可添加变量。")
            self.usage_text.setText("0%")
            self.usage_bar.set_usage(0, 1)
            self.db_heading.setText("尚无数据块")
            self.search.setEnabled(False)
            if plc:
                self.data_empty.set_content(
                    "database", "尚无数据块",
                    "为当前 PLC 新建一个数据块，然后添加变量开始模拟。",
                    "新建 DB", self.add_db, "plus",
                )
            else:
                self.data_empty.set_content(
                    "cpu", "还没有 PLC",
                    "创建一台 PLC 并添加数据块，即可开始模拟 S7 通信。",
                    "新增 PLC", self.add_plc, "plus",
                )
            self.data_stack.setCurrentWidget(self.data_empty)
        has_variables = bool(db and db.variables)
        self.table_hint.setVisible(has_variables)
        if has_variables and not self.inspector.isVisible():
            self.inspector.show()
            self.db_splitter.setSizes([max(560, self.db_splitter.width() - 310), 310])
        elif not has_variables:
            self.inspector.hide()
        self.data_table.blockSignals(False)
        self.building_table = False
        self.filter_table()
        row = (
            next((i for i, var in enumerate(db.variables) if var.id == self.selected_var_id), None)
            if db
            else None
        )
        if db and db.variables and row is None:
            row = next(
                (i for i, var in enumerate(db.variables) if var.dtype in NUMERIC and var.count == 1),
                0,
            )
        if db and db.variables:
            self.data_table.setCurrentCell(row, 0)
            self.variable_selected(row, 0, -1, -1)
        else:
            self.variable_selected(-1, -1, -1, -1)

    def filter_table(self):
        query = self.search.text().casefold()
        for row in range(self.data_table.rowCount()):
            parts = []
            for col in range(self.data_table.columnCount()):
                item = self.data_table.item(row, col)
                if item is not None:
                    parts.append(item.text())
            self.data_table.setRowHidden(row, query not in " ".join(parts).casefold())

    def variable_selected(self, row, col, old_row, old_col):
        db = self.db()
        var = db.variables[row] if db and 0 <= row < len(db.variables) else None
        self.selected_var_id = var.id if var else None
        self.sparkline.clear()
        self.var_live.setVisible(bool(var))
        if var:
            plc = self.plc()
            entry = self.engine.runtime(plc).layouts[db.id][row]
            dtype = var.dtype + (f"[{var.count}]" if var.count > 1 else "")
            self.var_name.setText(var.name)
            self.var_meta.setText(f"{dtype}  ·  {entry.address(db.number)}")
            values, _ = self.engine.runtime(plc).read_block(db)
            self.value_input.configure(var.dtype, var.count)
            self.value_input.setText(display_value(values[row][0]))
        else:
            self.var_name.setText("选择一个变量")
            self.var_meta.setText("添加变量后可在此修改数值与模拟规则")
            self.var_value.set_value("—")
            self.value_input.clear()
        self.refresh()

    # ------------------------------------------------------------------
    # live refresh

    def refresh(self):
        plc, db = self.plc(), self.db()
        runtime = self.engine.runtime(plc) if plc else None
        running = bool(runtime and runtime.running)
        stats = (
            runtime.statistics(include_history=self.tabs.currentIndex() in {1, 2})
            if runtime
            else {"connections": 0, "reads": 0, "writes": 0, "peers": [], "events": []}
        )
        cpu_running = running and int(runtime.server.cpu_state) == 8
        state = "RUN" if cpu_running else "CPU STOP" if running else "OFFLINE"
        self.state_pill.set_state(state)
        self.status_card.set_value(state)
        self.status_card.set_tone("ok" if cpu_running else "warn" if running else "muted")
        self.status_card.set_detail(plc.model + " · 经典 S7 TCP" if plc else "请新增一个 PLC")
        self.connection_card.set_value(str(stats["connections"]))
        self.connection_card.set_detail(f"最大 {plc.max_clients if plc else 0} 个连接")
        self.db_card.set_value(
            f"{len(plc.blocks)} / {sum(len(d.variables) for d in plc.blocks)}" if plc else "0 / 0"
        )
        self.db_card.set_detail(
            f"{sum(len(d.variables) for d in plc.blocks)} 个变量 · {len(plc.blocks)} 个 DB"
            if plc
            else "已配置的 DB 与变量"
        )
        self.io_card.set_value(f"{stats['reads']} / {stats['writes']}")

        self.run_button.setEnabled(plc is not None)
        self.run_button.setText("停止服务" if running else "启动服务")
        target_name = "stopButton" if running else "primary"
        if self.run_button.objectName() != target_name:
            self.run_button.setObjectName(target_name)
            repolish(self.run_button)
        desired = ["stop", "danger"] if running else ["play", "on_accent"]
        if self._icon_specs.get(self.run_button) != desired:
            self._icon_specs[self.run_button] = desired
            self._apply_icons()
        self.cpu_button.setEnabled(running)
        self.cpu_button.setText("CPU STOP" if cpu_running else "CPU RUN")
        self.config_button.setEnabled(plc is not None and not running)
        self.add_db_button.setEnabled(plc is not None and not running)
        self.edit_db_button.setEnabled(db is not None and not running)
        self.add_var_button.setEnabled(db is not None and not running)
        self.import_points_button.setEnabled(plc is not None and not running)
        index = self.variable_index()
        selected = index is not None
        if not selected:
            self.sim_start_button.hide()
        self.edit_var_button.setEnabled(selected and not running)
        self.delete_var_button.setEnabled(selected and not running)
        for widget in [self.value_input, self.write_button, self.sim_button, self.copy_button]:
            widget.setEnabled(selected)

        if plc:
            self.breadcrumb.setText(
                f"工作空间  /  {plc.name}  /  {'DB' + str(db.number) if db else 'PLC'}"
            )
            self.subtitle.setText(f"{plc.name}   ·   {plc.cpu}   ·   {plc.host}:{plc.port}")
            if running:
                elapsed = int(time.time() - runtime.started_at) if runtime.started_at else 0
                self.footer.setText(
                    f"{plc.host}:{plc.port}    ·    Rack {plc.rack} / Slot {plc.slot}"
                    f"    ·    已运行 {elapsed // 3600:02}:{elapsed // 60 % 60:02}:{elapsed % 60:02}"
                    "    ·    250 ms 采样"
                )
                self._set_footer_tone(self.colors.ok if cpu_running else self.colors.warn)
            else:
                self.footer.setText(
                    f"{plc.host}:{plc.port}    ·    Rack {plc.rack} / Slot {plc.slot}"
                    "    ·    服务未启动"
                )
                self._set_footer_tone(self.colors.text_faint)
        else:
            self.breadcrumb.setText("工作空间")
            self.subtitle.setText("新增 PLC，开始构建你的模拟环境。")
            self.footer.setText("本地模拟环境  ·  所有数值均为模拟数据")
            self._set_footer_tone(self.colors.text_faint)

        if db and runtime:
            values, _ = runtime.read_block(db)
            editing = self.data_table.state() == QAbstractItemView.State.EditingState
            self.data_table.blockSignals(True)
            for row, (value, error) in enumerate(values):
                if not editing:
                    item = self.data_table.item(row, 3)
                    if item is None:
                        continue
                    next_text = error or display_value(value)
                    key = (db.id, row)
                    if item.text() != next_text:
                        self.value_flashes[key] = time.monotonic()
                    age = time.monotonic() - self.value_flashes.get(key, 0)
                    strength = max(0.0, 1.0 - age / 0.9)
                    if strength > 0.02:
                        flash = QColor(self.colors.accent)
                        flash.setAlpha(int(46 * strength))
                        item.setBackground(flash)
                    else:
                        item.setData(Qt.ItemDataRole.BackgroundRole, None)
                    item.setText(next_text)
                    item.setToolTip(error or display_value(value))
                    item.setForeground(QColor(self.colors.danger if error else self.colors.accent))
                mode_item = self.data_table.item(row, 4)
                mode = db.variables[row].simulation.mode
                if mode_item is not None:
                    mode_item.setText(MODE_NAMES[mode])
                    mode_item.setForeground(
                        QColor(getattr(self.colors, MODE_COLORS.get(mode, "text_faint")))
                    )
            self.data_table.blockSignals(False)
            if index is not None:
                value, error = values[index]
                text = error or display_value(value)
                self.var_value.set_value(text if len(text) < 75 else text[:72] + "…", error=bool(error))
                self.var_value.setToolTip(text)
                var = db.variables[index]
                sim = var.simulation
                summary = MODE_NAMES[sim.mode]
                detail_text = summary
                if sim.mode != "manual":
                    summary += f" · {sim.interval_ms} ms"
                    detail_text += f"  ·  每 {sim.interval_ms} ms"
                    if var.dtype != "BOOL":
                        summary += f" · {sim.minimum:g}–{sim.maximum:g}"
                        detail_text += f"\n范围 {sim.minimum} – {sim.maximum}"
                if sim.mode != 'manual':
                    summary += ' · 模拟中' if cpu_running else ' · CPU 已暂停' if running else ' · 等待启动服务'
                detail_text += '\n自动模拟会在下一周期覆盖手动写入值。' if sim.mode != 'manual' else ''
                self.sim_start_button.setVisible(sim.mode != 'manual' and not cpu_running)
                self.sim_start_button.setText('恢复 CPU RUN' if running else '启动服务并模拟')
                self.sim_summary.setText(summary)
                self.sim_summary.setToolTip(detail_text)
                active = sim.mode != "manual"
                if self._sim_active != active:
                    self._sim_active = active
                    self.sim_summary.setProperty("active", active)
                    repolish(self.sim_summary)
                if not error:
                    self.sparkline.append(value)
        if self.tabs.currentIndex() == 1:
            self.render_connections(stats["peers"])
        if self.tabs.currentIndex() == 2:
            self.render_logs(stats["events"])

    def _set_footer_tone(self, color):
        if self._footer_tone == color:
            return
        self._footer_tone = color
        self.footer_dot.setStyleSheet(f"color: {color}; font-size: 9px;")

    def render_connections(self, peers):
        signature = (
            tuple((p["id"], p["disconnected_at"], p["reads"], p["writes"]) for p in peers),
            int(time.time()),
        )
        if signature == self.connection_signature:
            return
        self.connection_signature = signature
        active = sum(1 for p in peers if p["disconnected_at"] is None)
        self.conn_summary.setText(
            f"活跃 {active}    ·    会话 {len(peers)}    ·    "
            f"累计读 {sum(p['reads'] for p in peers)}    ·    累计写 {sum(p['writes'] for p in peers)}"
        )
        self.connection_table.setRowCount(len(peers))
        for row, peer in enumerate(peers):
            live = peer["disconnected_at"] is None
            elapsed = int((peer["disconnected_at"] or time.time()) - peer["connected_at"])
            values = [
                peer["ip"], peer["port"], "● 活跃" if live else "已断开",
                stamp(peer["connected_at"]), f"{elapsed // 60}m {elapsed % 60}s",
                peer["reads"], peer["writes"], f"{peer['bytes_read']} / {peer['bytes_written']} B",
            ]
            for col, value in enumerate(values):
                item = cell(value, not live)
                item.setToolTip(str(value))
                if col == 2 and live:
                    item.setForeground(QColor(self.colors.ok))
                if col in {5, 6, 7}:
                    item.setFont(mono_font(10))
                self.connection_table.setItem(row, col, item)
        self.connection_stack.setCurrentWidget(
            self.connection_table if peers else self.connection_empty
        )

    def render_logs(self, events):
        signature = (len(events), events[0]["time"] if events else None)
        if signature == self.log_signature:
            return
        self.log_signature = signature
        events = events[:300]
        self.log_table.setRowCount(len(events))
        for row, event in enumerate(events):
            kind = event["kind"]
            for col, value in enumerate(
                [stamp(event["time"]), kind, event["peer"], event["message"]]
            ):
                item = cell(value, col in {0, 2})
                item.setToolTip(str(value))
                if col == 1:
                    if kind == "ERROR":
                        color = self.colors.danger
                    elif kind in {"START", "STOP", "CPU", "EDIT", "SIM"}:
                        color = self.colors.accent
                    else:
                        color = self.colors.text_muted
                    item.setForeground(QColor(color))
                self.log_table.setItem(row, col, item)
        self.log_stack.setCurrentWidget(self.log_table if events else self.log_empty)

    # ------------------------------------------------------------------
    # structure operations

    def structural_allowed(self):
        plc = self.plc()
        if not plc:
            self.error("请先创建并选择一个 PLC")
            return False
        if self.engine.runtime(plc).running:
            self.error("请先停止当前 PLC 的服务，再修改配置或 DB 结构。数值和模拟规则可以在运行时修改。")
            return False
        self.engine.runtime(plc).snapshot_values()
        return True

    def commit_plc(self, replacement: PLC):
        candidate = clone(self.project)
        i = next((i for i, p in enumerate(candidate.plcs) if p.id == replacement.id), None)
        if i is None:
            candidate.plcs.append(replacement)
        else:
            candidate.plcs[i] = replacement
        candidate.validate()
        self.engine.rebuild(replacement)
        if i is None:
            self.project.plcs.append(replacement)
        else:
            self.project.plcs[i] = replacement
        self.plc_id = replacement.id
        self.mark_dirty()
        self.rebuild_tree()

    def add_plc(self):
        try:
            port = available_port(self.project.plcs)
        except ValueError as exc:
            self.error(exc)
            return
        plc = PLC(name=f"PLC {len(self.project.plcs) + 1:02}", port=port)
        dialog = PLCDialog(plc, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.commit_plc(dialog.result_value)
                self.notify(f"已新增 {dialog.result_value.name}", "success")
            except Exception as exc:
                self.error(exc)

    def edit_plc(self):
        if not self.structural_allowed():
            return
        dialog = PLCDialog(self.plc(), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.commit_plc(dialog.result_value)
                self.notify("PLC 配置已更新", "success")
            except Exception as exc:
                self.error(exc)

    def delete_plc(self):
        plc = self.plc()
        if not plc:
            return
        if QMessageBox.question(
            self, "删除 PLC", f"删除「{plc.name}」及其 {len(plc.blocks)} 个 DB？此操作无法撤销。"
            + ("\n服务将停止，现有客户端连接将断开。" if self.engine.runtime(plc).running else ""),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        self.engine.remove(plc)
        self.project.plcs.remove(plc)
        self.mark_dirty()
        self.rebuild_tree()
        self.notify("已删除 PLC", "info")

    def add_db(self):
        if not self.structural_allowed():
            return
        plc = self.plc()
        used = {db.number for db in plc.blocks}
        number = next((n for n in range(1, 65536) if n not in used), None)
        if number is None:
            self.error("DB 编号已用尽")
            return
        dialog = DBDialog(DataBlock(number=number, name=f"Data_Block_{number}"), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            replacement = clone(plc)
            replacement.blocks.append(dialog.result_value)
            self.db_id = dialog.result_value.id
            try:
                self.commit_plc(replacement)
                self.notify(f"已新建 DB{dialog.result_value.number}", "success")
            except Exception as exc:
                self.error(exc)

    def edit_db(self):
        if not self.db() or not self.structural_allowed():
            return
        dialog = DBDialog(self.db(), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            replacement = clone(self.plc())
            index = next(i for i, db in enumerate(replacement.blocks) if db.id == self.db_id)
            replacement.blocks[index] = dialog.result_value
            try:
                self.commit_plc(replacement)
                self.notify("数据块已更新", "success")
            except Exception as exc:
                self.error(exc)

    def duplicate_db(self):
        if not self.db() or not self.structural_allowed():
            return
        from .models import uid

        replacement = clone(self.plc())
        source = clone(self.db())
        used = {db.number for db in replacement.blocks}
        number = next((n for n in range(1, 65536) if n not in used), None)
        if number is None:
            self.error("DB 编号已用尽")
            return
        source.number, source.id, source.name = number, uid(), source.name + "_Copy"
        for var in source.variables:
            var.id = uid()
        replacement.blocks.append(source)
        self.db_id = source.id
        try:
            self.commit_plc(replacement)
            self.notify(f"已复制为 DB{number}", "success")
        except Exception as exc:
            self.error(exc)

    def delete_db(self):
        if not self.db() or not self.structural_allowed():
            return
        db = self.db()
        if QMessageBox.question(
            self, "删除数据块", f"删除 DB{db.number} · {db.name} 及其 {len(db.variables)} 个变量？此操作无法撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        replacement = clone(self.plc())
        replacement.blocks = [d for d in replacement.blocks if d.id != db.id]
        self.db_id = None
        try:
            self.commit_plc(replacement)
            self.notify("数据块已删除", "info")
        except Exception as exc:
            self.error(exc)

    def import_points(self):
        if not self.structural_allowed():
            return
        dialog = PointImportDialog(self.plc(), self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result_value is not None:
            try:
                self.commit_plc(dialog.result_value)
                self.notify("点位已批量导入", "success")
            except Exception as exc:
                self.error(exc)

    def add_variable(self):
        self.edit_variable(adding=True)

    def edit_variable(self, checked=False, adding=False):
        if not self.db() or not self.structural_allowed():
            return
        index = self.variable_index()
        if index is None and not adding:
            return
        dialog = VariableDialog(None if adding else self.db().variables[index], self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            replacement = clone(self.plc())
            db = next(d for d in replacement.blocks if d.id == self.db_id)
            if adding:
                db.variables.append(dialog.result_value)
            else:
                db.variables[index] = dialog.result_value
            self.selected_var_id = dialog.result_value.id
            try:
                self.commit_plc(replacement)
                self.notify(
                    f"{'已新增' if adding else '已更新'}变量 {dialog.result_value.name}", "success"
                )
            except Exception as exc:
                self.error(exc)

    def delete_variable(self):
        index = self.variable_index()
        if index is None or not self.structural_allowed():
            return
        replacement = clone(self.plc())
        db = next(d for d in replacement.blocks if d.id == self.db_id)
        name = db.variables[index].name
        if QMessageBox.question(
            self, "删除变量", f"删除变量 {name}？后续变量地址将自动重新排列。"
        ) != QMessageBox.StandardButton.Yes:
            return
        db.variables.pop(index)
        try:
            self.commit_plc(replacement)
            self.notify(f"已删除变量 {name}", "info")
        except Exception as exc:
            self.error(exc)

    def value_edited(self, item):
        if self.building_table or item.column() not in {1, 2, 3, 6, 8}:
            return
        db, plc = self.db(), self.plc()
        if not db or not plc:
            return
        var = db.variables[item.row()]
        if item.column() in {1, 2, 6, 8}:
            if not self.structural_allowed():
                self.populate_table()
                return
            try:
                replacement = clone(plc)
                target = next(d for d in replacement.blocks if d.id == db.id).variables[item.row()]
                if item.column() == 1:
                    dtype = item.text()
                    if dtype not in TYPES:
                        raise ValueError("请选择有效的数据类型")
                    if dtype != target.dtype:
                        target.dtype = dtype
                        target.value = default_value(dtype, target.count)
                        target.simulation = Simulation()
                        target.bit_offset = 0
                        target.storage_size = None
                elif item.column() == 8:
                    target.length = int(item.text())
                elif item.column() == 2:
                    text = item.text().strip()
                    parts = text.split(".")
                    if len(parts) > 2:
                        raise ValueError("地址格式为 字节.位")
                    target.offset = int(parts[0]) if text else None
                    target.bit_offset = int(parts[1]) if len(parts) == 2 else 0
                else:
                    target.storage_size = int(item.text()) or None
                self.commit_plc(replacement)
            except Exception as exc:
                self.error(exc)
                self.populate_table()
            return
        try:
            value = parse_input(item.text(), var.dtype, var.count)
            self.engine.runtime(plc).set_value(db, item.row(), value)
            self.mark_dirty()
            self.value_flashes[(db.id, item.row())] = time.monotonic()
        except Exception as exc:
            self.error(exc)
        self.refresh()

    def write_selected_value(self):
        index = self.variable_index()
        if index is None:
            return
        db, plc = self.db(), self.plc()
        var = db.variables[index]
        try:
            value = parse_input(self.value_input.text(), var.dtype, var.count)
            self.engine.runtime(plc).set_value(db, index, value)
            self.mark_dirty()
            suffix = "；下次自动模拟更新将覆盖此值" if var.simulation.mode != "manual" else ""
            self.notify(f"已写入 {var.name} = {display_value(value)}{suffix}", "success")
        except Exception as exc:
            self.error(exc)
        self.refresh()

    def copy_value(self):
        index = self.variable_index()
        if index is None:
            return
        values, _ = self.engine.runtime(self.plc()).read_block(self.db())
        value, error = values[index]
        if error:
            self.error(error)
            return
        QApplication.clipboard().setText(display_value(value))
        self.notify("当前值已复制到剪贴板", "info")

    def start_simulation(self):
        plc = self.plc()
        if not plc:
            return
        runtime = self.engine.runtime(plc)
        try:
            if not runtime.running:
                runtime.start()
            runtime.server.set_cpu_status(8)
            self.update_tree_status()
            self.refresh()
            self.notify('服务已启动，CPU RUN：自动模拟开始更新', 'success')
        except Exception as exc:
            self.error(exc)

    def configure_simulation(self):
        index = self.variable_index()
        if index is None:
            return
        db, plc = self.db(), self.plc()
        dialog = SimulationDialog(db.variables[index], self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.engine.runtime(plc).set_simulation(db, index, dialog.result_value)
            self.mark_dirty()
            self.notify("模拟规则已更新", "success")
            self.refresh()

    # ------------------------------------------------------------------
    # service

    def toggle_server(self):
        plc = self.plc()
        if not plc:
            return
        runtime = self.engine.runtime(plc)
        was_running = runtime.running
        try:
            runtime.stop() if was_running else runtime.start()
        except Exception as exc:
            self.error(f"无法启动 {plc.host}:{plc.port}\n\n{exc}\n\n请检查端口占用、监听地址或系统权限。")
        else:
            if was_running:
                self.notify(f"服务已停止 · {plc.host}:{plc.port}", "info")
            else:
                self.notify(f"S7 服务已启动 · {plc.host}:{plc.port}", "success")
        self.update_tree_status()
        self.refresh()

    def update_tree_status(self):
        for index, plc in enumerate(self.project.plcs):
            item = self.tree.topLevelItem(index)
            if item is not None:
                item.setData(0, ROLE_RUNNING, bool(self.engine.runtime(plc).running))
        self.tree.viewport().update()

    def toggle_cpu(self):
        plc = self.plc()
        if plc and self.engine.runtime(plc).running:
            runtime = self.engine.runtime(plc)
            status = 4 if int(runtime.server.cpu_state) == 8 else 8
            runtime.server.set_cpu_status(status)
            runtime.add_event("CPU", "CPU → RUN" if status == 8 else "CPU → STOP")
            self.notify("CPU 已切换到 RUN" if status == 8 else "CPU 已切换到 STOP", "info")
            self.refresh()

    def start_all(self):
        errors = []
        for plc in self.project.plcs:
            try:
                self.engine.runtime(plc).start()
            except Exception as exc:
                errors.append(f"{plc.name}: {exc}")
        self.update_tree_status()
        self.refresh()
        if errors:
            self.error("\n".join(errors))
        else:
            self.notify(f"已启动 {len(self.project.plcs)} 个服务", "success")

    def stop_all(self):
        for plc in self.project.plcs:
            self.engine.runtime(plc).stop()
        self.update_tree_status()
        self.refresh()
        self.notify("已停止全部服务", "info")

    # ------------------------------------------------------------------
    # files

    def storage_settings(self):
        dialog = StorageDialog(default_directory(self.settings), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings.setValue('files/default_directory', str(dialog.result_value))
            self.settings.sync()
            if self.settings.status() != QSettings.Status.NoError:
                self.error('系统未能持久保存目录设置，请检查用户配置权限')
            else:
                self.notify(f'默认保存目录已更新 · {dialog.result_value}', 'success')

    def maybe_save(self):
        if not self.dirty:
            return True
        answer = QMessageBox.question(
            self, "保存项目", "项目有未保存的修改，是否保存？",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        return self.save_project() if answer == QMessageBox.StandardButton.Save else True

    def replace_project(self, project, path=None):
        self.engine.close()
        self.project = project
        self.engine = Engine(project)
        self.path = path
        self.dirty = False
        self.plc_id = self.db_id = self.selected_var_id = None
        self.value_flashes.clear()
        self.log_signature = self.connection_signature = None
        self.search.clear()
        self.tabs.setCurrentIndex(0)
        self.rebuild_tree()
        self.update_title()
        self.refresh()

    def new_project(self):
        if self.maybe_save():
            self.replace_project(Project())
            self.notify("已新建空项目", "info")

    def load_demo(self):
        if self.maybe_save():
            self.replace_project(demo_project())
            self.notify("已加载示例项目", "success")

    def open_project(self):
        if not self.maybe_save():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "打开 S7 项目", str(self.path.parent if self.path else default_directory(self.settings)), "S7 项目 (*.s7sim.json *.json)"
        )
        if path:
            try:
                project = Project.load(path)
                self.replace_project(project, Path(path))
                self.notify(f"已打开 {Path(path).name}", "success")
            except Exception as exc:
                self.error(exc)

    def save_project(self):
        if self.path is None:
            return self.save_as()
        try:
            self.engine.snapshot()
            self.project.save(self.path)
            db = self.db()
            if db:
                self.data_table.blockSignals(True)
                for row, var in enumerate(db.variables):
                    item = self.data_table.item(row, 7)
                    if item:
                        item.setText(display_value(var.value))
                self.data_table.blockSignals(False)
            self.dirty = False
            self.update_title()
            self.notify(f"项目已保存 · {self.path.name}", "success")
            return True
        except Exception as exc:
            self.error(exc)
            return False

    def save_as(self):
        try:
            initial = self.path or suggested_path(self.settings, self.project.name)
        except OSError as exc:
            self.error(f'默认目录不可用，请通过「文件 → 项目保存设置」修改。\n{exc}')
            return False
        path, _ = QFileDialog.getSaveFileName(
            self, "保存 S7 项目", str(initial),
            "S7 项目 (*.s7sim.json)",
        )
        if not path:
            return False
        previous = self.path
        target = Path(path if path.lower().endswith('.json') else path + '.s7sim.json')
        if str(target) != path and target.exists():
            if QMessageBox.question(self, '覆盖项目', f'{target.name} 已存在，是否覆盖？') != QMessageBox.StandardButton.Yes:
                return False
        self.path = target
        if self.save_project():
            return True
        self.path = previous
        self.update_title()
        return False

    def export_db(self):
        db, plc = self.db(), self.plc()
        if not db or not plc:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 DB 定义", f"DB{db.number}.csv", "CSV (*.csv)"
        )
        if not path:
            return
        try:
            runtime = self.engine.runtime(plc)
            values, _ = runtime.read_block(db)
            with open(path, "w", encoding="utf-8-sig", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(
                    ["Name", "Type", "Count", "StringCapacity", "Address", "Value", "Simulation", "Comment"]
                )
                for var, entry, (value, error) in zip(db.variables, runtime.layouts[db.id], values):
                    writer.writerow([
                        var.name, var.dtype, var.count, var.length,
                        entry.address(db.number), error or display_value(value),
                        var.simulation.mode, var.comment,
                    ])
            self.notify(f"DB 定义已导出 · {Path(path).name}", "success")
        except Exception as exc:
            self.error(exc)

    def export_logs(self):
        plc = self.plc()
        if not plc:
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出事件日志", "s7-events.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(["Time", "PLC", "Event", "Peer", "Message"])
                for event in reversed(self.engine.runtime(plc).statistics()["events"]):
                    writer.writerow([
                        dt.datetime.fromtimestamp(event["time"]).isoformat(),
                        plc.name, event["kind"], event["peer"], event["message"],
                    ])
            self.notify(f"事件日志已导出 · {Path(path).name}", "success")
        except Exception as exc:
            self.error(exc)

    def clear_logs(self):
        plc = self.plc()
        if plc:
            runtime = self.engine.runtime(plc)
            with runtime.lock:
                runtime.events.clear()
            self.log_signature = None
            self.refresh()
            self.notify("事件日志已清空", "info")

    # ------------------------------------------------------------------
    # help / copy helpers

    def _client_snippet(self, plc=None, db=None):
        plc = plc or self.plc() or PLC()
        db = db or self.db()
        number = db.number if db else 1
        host = "127.0.0.1" if plc.host == "0.0.0.0" else plc.host
        return (
            "import snap7\n\n"
            "client = snap7.Client()\n"
            f"client.connect('{host}', {plc.rack}, {plc.slot}, tcp_port={plc.port})\n"
            f"data = client.db_read({number}, 0, 16)\n"
            "print(data.hex(' '))\n"
            "client.disconnect()\n"
            "client.destroy()\n"
        )

    def copy_client_example(self):
        QApplication.clipboard().setText(self._client_snippet())
        self.notify("连接示例已复制到剪贴板", "success")

    def show_help(self):
        plc = self.plc() or PLC()
        db = self.db()
        number = db.number if db else 1
        host = "127.0.0.1" if plc.host == "0.0.0.0" else plc.host
        snippet = self._client_snippet(plc, db)
        code = html.escape(snippet)

        dialog = QDialog(self)
        dialog.setWindowTitle("连接示例与功能范围")
        dialog.resize(790, 650)
        dialog.setMinimumSize(720, 580)
        outer = QVBoxLayout(dialog)
        outer.setContentsMargins(22, 20, 22, 18)
        outer.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(12)
        header.addWidget(IconTile("book", "accent", 42))
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(label("连接示例与功能范围", "dialogTitle"))
        titles.addWidget(label("标准非优化 DB · 经典 S7 TCP", "dialogSubtitle"))
        header.addLayout(titles, 1)
        outer.addLayout(header)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.setTabBar(PillTabBar())
        example = QTextBrowser()
        example.setHtml(
            "<h3>Python 示例（python-snap7 3.2.1）</h3>"
            f"<pre style=\"font-family: Menlo, Consolas, monospace; font-size: 11px;\">{code}</pre>"
            "<p>1. 启动当前 PLC 的 S7 服务。</p>"
            "<p>2. 客户端指定 IPv4、TCP 端口及推荐 Rack / Slot。</p>"
            "<p>3. 按工作台显示的绝对地址访问标准非优化 DB。</p>"
            "<h3>其他客户端</h3>"
            "<p>S7.Net / Sharp7 / HslCommunication 等需设置相同端口。"
            "不支持自定义端口的客户端需要将服务端口改为 102。"
            "局域网连接可将监听地址设为 0.0.0.0，客户端使用此电脑的局域网 IP。</p>"
        )
        support = QTextBrowser()
        support.setHtml(
            "<h3>支持范围</h3><ul>"
            "<li>多 PLC 实例、数据块、标量与一维数组、标准 S7 数据类型。</li>"
            "<li>运行中手动写值、客户端读写、随机 / 正弦 / 斜坡 / BOOL 翻转。</li>"
            "<li>CPU RUN / STOP、客户端 IP 和端口、读写计数、事件日志。</li>"
            "<li>JSON 项目保存与加载、CSV 定义及日志导出。</li>"
            "</ul><h3>工作流</h3>"
            "<p>启动服务 → 客户端连接 → 在数据块表格或检查器中改值 → 观察连接与事件日志。"
            "结构调整（增删 PLC / DB / 变量）需先停止服务。</p>"
        )
        limits = QTextBrowser()
        limits.setHtml(
            "<h3>边界说明</h3>"
            "<p>型号与 CPU 名称为配置预设；SZL 返回预设 CPU 名称及带 SIM 标识的模拟序列号、订货号，"
            "不模拟特定 CPU 固件或资源限制。Rack / Slot 不强制校验。</p>"
            "<p>不执行梯形图、STL、SCL 或 TIA 工程；不提供 S7 Plus、优化 DB、OPC UA 或硬件 I/O 仿真。</p>"
            "<p>BOOL 连续位打包，其余多字节类型按偶数字节对齐；数组按元素顺序连续存储。</p>"
        )
        tabs.addTab(example, "连接示例")
        tabs.addTab(support, "支持范围")
        tabs.addTab(limits, "边界说明")
        outer.addWidget(tabs, 1)

        note = label("", "fieldHint")
        footer = QHBoxLayout()
        footer.addWidget(note, 1)
        copy = button("复制 Python 示例", None)
        copy.setObjectName("softButton")
        copy.setIcon(icons.make_icon("copy", self.colors.accent, 15))
        copy.setIconSize(QSize(15, 15))

        def copy_example():
            QApplication.clipboard().setText(snippet)
            note.setText("示例已复制到剪贴板")

        copy.clicked.connect(copy_example)
        close = button("关闭", dialog.accept, "primary")
        close.setIcon(icons.make_icon("check", self.colors.on_accent, 15))
        close.setIconSize(QSize(15, 15))
        footer.addWidget(copy)
        footer.addWidget(close)
        outer.addLayout(footer)
        dialog.exec()

    def closeEvent(self, event):
        if not self.maybe_save():
            event.ignore()
            return
        self.timer.stop()
        toaster = getattr(self, "toaster", None)
        if toaster is not None:
            toaster.timer.stop()
        self.engine.close()
        event.accept()
