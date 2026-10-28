"""Design tokens, application palettes and the style sheet.

The UI deliberately owns a small token system instead of patching colours with
regular expressions.  Both themes are generated from the same layout rules, so
new widgets only need to reference semantic tokens (surface, accent, danger…)
and immediately work in light and dark mode.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from string import Template

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


MONO_FONT = '"SF Mono", "Menlo", "Cascadia Mono", "Consolas", "Liberation Mono", monospace'


@dataclass(frozen=True)
class Palette:
    name: str = "light"

    # Canvas -----------------------------------------------------------------
    bg: str = "#f2f6f7"
    bg_top: str = "#f8fbfc"
    surface: str = "#ffffff"
    surface_alt: str = "#f6f9fa"
    surface_hover: str = "#f0f6f7"
    surface_press: str = "#e8f2f3"
    border: str = "#e2eaec"
    border_strong: str = "#cbd9dd"
    grid: str = "#edf2f3"

    # Type -------------------------------------------------------------------
    text: str = "#152a31"
    text_muted: str = "#5f757c"
    text_faint: str = "#93a5aa"

    # Accent -----------------------------------------------------------------
    accent: str = "#0b8f7d"
    accent_hover: str = "#0aa391"
    accent_strong: str = "#076f61"
    accent_soft: str = "#e4f4f0"
    accent_soft_hover: str = "#d7efe9"
    accent_line: str = "#bfe6dd"
    on_accent: str = "#ffffff"
    accent_grad_a: str = "#10a391"
    accent_grad_b: str = "#087f70"
    accent_grad_a_hover: str = "#12b19e"
    accent_grad_b_hover: str = "#0a9181"

    # Semantic ---------------------------------------------------------------
    ok: str = "#0f9d76"
    ok_soft: str = "#e3f5ee"
    warn: str = "#b7791f"
    warn_soft: str = "#fbf1de"
    danger: str = "#c2412d"
    danger_soft: str = "#fcebe7"
    danger_soft_hover: str = "#f9ded8"
    danger_line: str = "#f0c4ba"
    info: str = "#2d6fbf"
    info_soft: str = "#e8f1fb"

    # Sidebar ----------------------------------------------------------------
    sidebar: str = "#081a20"
    sidebar_alt: str = "#0b242b"
    sidebar_text: str = "#d8e6ea"
    sidebar_muted: str = "#75949c"
    sidebar_border: str = "#1a343b"
    sidebar_button: str = "#0f2a31"
    sidebar_button_hover: str = "#15363e"

    # Data views -------------------------------------------------------------
    selection: str = "#e3f4ef"
    selection_text: str = "#0a5c50"
    row_alt: str = "#f8fbfc"
    header: str = "#f7fafb"
    scroll: str = "#cddadd"
    scroll_hover: str = "#a9bec4"

    # Misc -------------------------------------------------------------------
    shadow: str = "#0a1e24"
    code_bg: str = "#f3f8f8"
    chart_grid: str = "#e5edee"
    tooltip_bg: str = "#081a20"
    tooltip_text: str = "#e6f2f4"

    # Data type accents ------------------------------------------------------
    type_bool: str = "#7c5ce0"
    type_int: str = "#2d7dd2"
    type_float: str = "#0b8f7d"
    type_string: str = "#b7791f"
    type_time: str = "#b84f78"

    mono: str = MONO_FONT


DARK = Palette(
    name="dark",
    bg="#091216",
    bg_top="#0c181e",
    surface="#0f1c23",
    surface_alt="#14242d",
    surface_hover="#182b35",
    surface_press="#1c333e",
    border="#20333d",
    border_strong="#2d4551",
    grid="#172831",
    text="#e3eef2",
    text_muted="#93a9b2",
    text_faint="#667f89",
    accent="#31d2b7",
    accent_hover="#4ce0c7",
    accent_strong="#16a48d",
    accent_soft="#11332e",
    accent_soft_hover="#164039",
    accent_line="#1d4b43",
    on_accent="#052420",
    accent_grad_a="#3bdcc1",
    accent_grad_b="#22b79e",
    accent_grad_a_hover="#55e8cf",
    accent_grad_b_hover="#2ac7ab",
    ok="#3ed6a4",
    ok_soft="#0f2c25",
    warn="#f2b85b",
    warn_soft="#33270f",
    danger="#f58b72",
    danger_soft="#3a211b",
    danger_soft_hover="#48271f",
    danger_line="#5a3027",
    info="#79b5f2",
    info_soft="#122a3f",
    sidebar="#050f13",
    sidebar_alt="#08181e",
    sidebar_text="#d8e8ec",
    sidebar_muted="#6c8b94",
    sidebar_border="#11242b",
    sidebar_button="#0c2228",
    sidebar_button_hover="#123039",
    selection="#123833",
    selection_text="#cffff5",
    row_alt="#0c181e",
    header="#0d1a21",
    scroll="#283d47",
    scroll_hover="#3a5561",
    shadow="#000000",
    code_bg="#0b161c",
    chart_grid="#1b2d36",
    tooltip_bg="#061014",
    tooltip_text="#dcebef",
    type_bool="#b29cff",
    type_int="#79b8ff",
    type_float="#4fe0c6",
    type_string="#f2c46d",
    type_time="#f49ac1",
)

LIGHT = Palette()

_CURRENT: Palette = LIGHT


def palette_for(dark: bool) -> Palette:
    return DARK if dark else LIGHT


def current() -> Palette:
    return _CURRENT


def qpalette(colors: Palette) -> QPalette:
    """Build a palette so native sub-controls (arrows, menus, dialogs) match."""

    pal = QPalette()
    roles = {
        QPalette.ColorRole.Window: colors.bg,
        QPalette.ColorRole.WindowText: colors.text,
        QPalette.ColorRole.Base: colors.surface,
        QPalette.ColorRole.AlternateBase: colors.row_alt,
        QPalette.ColorRole.Text: colors.text,
        QPalette.ColorRole.Button: colors.surface,
        QPalette.ColorRole.ButtonText: colors.text,
        QPalette.ColorRole.BrightText: colors.danger,
        QPalette.ColorRole.Highlight: colors.accent,
        QPalette.ColorRole.HighlightedText: colors.on_accent,
        QPalette.ColorRole.Link: colors.accent,
        QPalette.ColorRole.LinkVisited: colors.accent_strong,
        QPalette.ColorRole.ToolTipBase: colors.tooltip_bg,
        QPalette.ColorRole.ToolTipText: colors.tooltip_text,
        QPalette.ColorRole.PlaceholderText: colors.text_faint,
        QPalette.ColorRole.Light: colors.border,
        QPalette.ColorRole.Midlight: colors.surface_alt,
        QPalette.ColorRole.Mid: colors.border,
        QPalette.ColorRole.Dark: colors.border_strong,
        QPalette.ColorRole.Shadow: colors.shadow,
    }
    accent_role = getattr(QPalette.ColorRole, "Accent", None)
    if accent_role is not None:
        roles[accent_role] = colors.accent
    for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
        for role, value in roles.items():
            pal.setColor(group, role, QColor(value))
    for role, value in roles.items():
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor(value))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.PlaceholderText,
        QPalette.ColorRole.Link,
    ):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor(colors.text_faint))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base, QColor(colors.surface_alt))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button, QColor(colors.surface_alt))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Highlight, QColor(colors.accent_soft))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.HighlightedText, QColor(colors.text_faint))
    return pal


_QSS = Template(
    """
QMainWindow, QDialog { background: $bg; }
QWidget { color: $text; font-size: 13px; }
QWidget#appRoot { background: $bg; }
QWidget#content { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 $bg_top, stop:1 $bg); }
QWidget#sidebar { background: transparent; }
QWidget#inspectorInner, QWidget#scrollBody { background: transparent; }

QFrame#card, QFrame#panel { background: $surface; border: 1px solid $border; border-radius: 12px; }
QFrame#valueBox { background: $surface_alt; border: 1px solid $border; border-radius: 10px; }
QFrame#hintBar { background: $surface_alt; border: 1px solid $border; border-radius: 10px; }
QFrame#dialogCard { background: $surface; border: 1px solid $border; border-radius: 15px; }
QFrame#divider { background: $border; border: none; min-height: 1px; max-height: 1px; }
QFrame#sideDivider { background: $sidebar_border; border: none; min-height: 1px; max-height: 1px; }
QFrame#emptyState { background: transparent; border: none; }

QLabel { background: transparent; }
QLabel#muted { color: $text_muted; }
QLabel#breadcrumb { color: $text_faint; font-size: 12px; }
QLabel#projectChip {
    background: $surface_alt; border: 1px solid $border; border-radius: 8px;
    padding: 5px 10px; color: $text_muted; font-size: 11.5px;
}
QLabel#projectChip[dirty="true"] { background: $warn_soft; border-color: $warn; color: $warn; }
QLabel#pageTitle { color: $text; font-size: 25px; font-weight: 700; }
QLabel#subtitle { color: $text_muted; font-size: 12.5px; }
QLabel#sectionTitle { color: $text; font-size: 15px; font-weight: 650; }
QLabel#cardCaption { color: $text_muted; font-size: 11.5px; font-weight: 600; }
QLabel#cardDetail { color: $text_faint; font-size: 11.5px; }
QLabel#varName { color: $text; font-size: 19px; font-weight: 650; }
QLabel#varMeta { color: $text_faint; font-family: $mono; font-size: 11px; }
QLabel#simSummary { color: $text_faint; font-size: 11.5px; }
QLabel#simSummary[active="true"] { color: $accent; }
QLabel#trendTitle { color: $text_muted; font-size: 12px; font-weight: 600; }
QLabel#fieldHint { color: $text_faint; font-size: 10.5px; }
QLabel#memoryLabel { color: $text_faint; font-size: 11px; }
QLabel#statusText { color: $text_faint; font-size: 11px; }
QLabel#countBadge {
    background: $accent_soft; border: 1px solid $accent_line; border-radius: 9px;
    color: $accent; padding: 3px 9px; font-size: 10.5px; font-weight: 600;
}
QLabel#dbChip {
    background: $accent_soft; border: 1px solid $accent_line; border-radius: 6px;
    color: $accent; padding: 2px 7px; font-family: $mono; font-size: 10.5px; font-weight: 600;
}
QLabel#readonly {
    background: $surface_alt; border: 1px solid $border; border-radius: 7px;
    color: $text_muted; padding: 6px 9px; font-family: $mono; font-size: 11px;
}
QDialog { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 $bg_top, stop:1 $bg); }
QLabel#dialogTitle { color: $text; font-size: 21px; font-weight: 700; }
QLabel#dialogSubtitle { color: $text_muted; font-size: 12px; }
QLabel#formLabel { color: $text_muted; font-size: 12px; }
QLabel#formSection {
    color: $text_faint; font-size: 10px; font-weight: 700; padding-top: 5px;
}
QFrame#dialogError {
    background: $danger_soft; border: 1px solid $danger_line; border-radius: 9px;
}
QLabel#dialogErrorText { color: $danger; font-size: 11.5px; font-weight: 550; }
QLabel#simPreview {
    background: $accent_soft; border: 1px solid $accent_line; border-radius: 8px;
    color: $accent_strong; padding: 9px 11px; font-size: 12px;
}
QLabel#emptyTitle { color: $text; font-size: 16px; font-weight: 650; }
QLabel#emptyText { color: $text_muted; font-size: 12px; }
QLabel#hintText { color: $text_muted; font-size: 11.5px; }
QLabel#sideLabel { color: $sidebar_muted; font-size: 10px; font-weight: 700; }
QLabel#sideCount { color: $sidebar_muted; font-size: 10px; }
QLabel#sideFoot { color: $sidebar_muted; font-size: 9.5px; }
QLabel#brandTitle { color: $sidebar_text; font-size: 16px; font-weight: 700; }
QLabel#brandSub { color: $sidebar_muted; font-size: 9px; font-weight: 600; }

QPushButton {
    background: $surface; color: $text; border: 1px solid $border; border-radius: 8px;
    padding: 6px 12px; min-height: 21px; font-weight: 500; text-align: center;
}
QPushButton:hover { background: $surface_hover; border-color: $border_strong; }
QPushButton:pressed { background: $surface_press; }
QPushButton:focus { border-color: $accent_line; }
QPushButton:disabled { background: $surface_alt; color: $text_faint; border-color: $border; }
QPushButton#primary {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 $accent_grad_a, stop:1 $accent_grad_b);
    color: $on_accent; border: 1px solid $accent_grad_b; font-weight: 650;
}
QPushButton#primary:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 $accent_grad_a_hover, stop:1 $accent_grad_b_hover);
    border-color: $accent_grad_b_hover;
}
QPushButton#primary:pressed { background: $accent_strong; border-color: $accent_strong; }
QPushButton#primary:disabled { background: $surface_alt; color: $text_faint; border-color: $border; }
QPushButton#compactPrimary {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 $accent_grad_a, stop:1 $accent_grad_b);
    color: $on_accent; border: 1px solid $accent_grad_b; border-radius: 7px;
    padding: 5px 10px; font-weight: 650; min-height: 19px;
}
QPushButton#compactPrimary:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 $accent_grad_a_hover, stop:1 $accent_grad_b_hover);
}
QPushButton#stopButton {
    background: $danger_soft; color: $danger; border: 1px solid $danger_line; font-weight: 650;
}
QPushButton#stopButton:hover { background: $danger_soft_hover; border-color: $danger; }
QPushButton#softButton {
    background: $accent_soft; color: $accent; border: 1px solid $accent_line; font-weight: 600;
}
QPushButton#softButton:hover { background: $accent_soft_hover; border-color: $accent; }
QPushButton#ghost {
    background: transparent; border-color: transparent; color: $text_muted; font-weight: 500;
}
QPushButton#ghost:hover { background: $surface_hover; color: $text; border-color: transparent; }
QPushButton#iconButton {
    background: transparent; border-color: transparent; border-radius: 8px; padding: 5px;
}
QPushButton#iconButton:hover { background: $surface_hover; }
QPushButton#danger { color: $danger; }
QPushButton#danger:hover { background: $danger_soft; border-color: $danger_line; color: $danger; }
QPushButton#sidebarButton {
    background: $sidebar_button; color: $sidebar_text; border: 1px solid $sidebar_border;
    border-radius: 9px; padding: 8px 12px; font-weight: 550;
}
QPushButton#sidebarButton:hover { background: $sidebar_button_hover; border-color: $accent_line; }
QPushButton#smallButton { padding: 4px 9px; font-size: 11.5px; min-height: 18px; }
QPushButton#smallSoftButton {
    background: $accent_soft; color: $accent; border: 1px solid $accent_line;
    border-radius: 7px; padding: 4px 9px; font-size: 11.5px; min-height: 18px; font-weight: 600;
}
QPushButton#smallSoftButton:hover { background: $accent_soft_hover; border-color: $accent; }
QPushButton#smallSoftButton:disabled {
    background: $surface_alt; color: $text_faint; border-color: $border;
}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QAbstractSpinBox {
    background: $surface; color: $text; border: 1px solid $border; border-radius: 8px;
    padding: 6px 10px; min-height: 20px;
    selection-background-color: $accent_soft; selection-color: $accent_strong;
}
QLineEdit:hover, QSpinBox:hover, QComboBox:hover, QAbstractSpinBox:hover { border-color: $border_strong; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QAbstractSpinBox:focus {
    border-color: $accent; background: $surface;
}
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled, QAbstractSpinBox:disabled {
    background: $surface_alt; color: $text_faint; border-color: $border;
}
QLineEdit[readOnly="true"] { background: $surface_alt; color: $text_muted; }
QLineEdit#valueInput { font-family: $mono; font-size: 12.5px; padding: 7px 10px; }
QLineEdit#searchField { padding-left: 8px; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox::down-arrow { image: none; }
QComboBox QAbstractItemView {
    background: $surface; border: 1px solid $border; border-radius: 8px; padding: 4px;
    color: $text; outline: 0;
    selection-background-color: $accent_soft; selection-color: $accent_strong;
}
QComboBox QAbstractItemView::item { padding: 6px 8px; border-radius: 5px; min-height: 20px; }
QSpinBox::up-button, QDoubleSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::down-button {
    width: 17px; border: none; background: transparent;
}
QSpinBox::up-arrow, QSpinBox::down-arrow { image: none; }

QTableWidget {
    background: $surface; alternate-background-color: $row_alt;
    border: none; gridline-color: $grid; outline: 0;
    selection-background-color: $selection; selection-color: $selection_text;
}
QTableWidget::item { padding: 0 10px; border-bottom: 1px solid $grid; }
QTableWidget::item:hover { background: $surface_hover; }
QTableWidget::item:selected { background: $selection; color: $selection_text; }
QTableWidget QLineEdit, QTableWidget QComboBox, QTableWidget QSpinBox {
    padding: 2px 6px; min-height: 24px; border-radius: 5px;
}
QHeaderView::section {
    background: $header; color: $text_faint; font-size: 10.5px; font-weight: 600;
    border: none; border-bottom: 1px solid $border; padding: 9px 10px;
}
QHeaderView::section:vertical {
    background: $surface; color: $text_faint; font-size: 9.5px;
    border: none; border-bottom: 1px solid $grid; padding: 0 6px;
}
QTableCornerButton::section { background: $header; border: none; }

QTabWidget::pane { border: none; background: transparent; }
QTabBar { background: transparent; }
QTabBar::tab {
    background: transparent; color: $text_muted; border: none; border-radius: 8px;
    padding: 7px 16px; margin-right: 3px; font-weight: 500; outline: 0;
}
QTabBar::tab:hover { color: $text; background: $surface_hover; }
QTabBar::tab:selected { color: $accent; font-weight: 650; }

QTreeWidget#projectTree {
    background: transparent; border: none; color: $sidebar_text; outline: 0;
    show-decoration-selected: 0;
}
QTreeWidget#projectTree::item { background: transparent; border: none; padding: 0; }
QTreeWidget#projectTree::item:selected, QTreeWidget#projectTree::item:hover { background: transparent; }
QTreeWidget#projectTree::branch { background: transparent; }
QTreeWidget#projectTree::branch:hover { background: transparent; }

QMenuBar { background: $surface; color: $text_muted; border-bottom: 1px solid $border; padding: 2px 4px; }
QMenuBar::item { background: transparent; padding: 5px 9px; border-radius: 6px; }
QMenuBar::item:selected { background: $accent_soft; color: $accent; }
QMenu {
    background: $surface; border: 1px solid $border; border-radius: 9px; padding: 6px;
}
QMenu::item { background: transparent; color: $text; padding: 7px 26px 7px 24px; border-radius: 6px; }
QMenu::item:selected { background: $accent_soft; color: $accent_strong; }
QMenu::item:disabled { color: $text_faint; }
QMenu::separator { height: 1px; background: $border; margin: 5px 8px; }
QMenu::indicator { width: 15px; height: 15px; }

QSplitter::handle { background: transparent; }
QSplitter::handle:hover { background: $accent_line; border-radius: 2px; }

QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px 2px 2px 0; }
QScrollBar::handle:vertical { background: $scroll; border-radius: 3px; min-height: 28px; margin: 0 2px; }
QScrollBar::handle:vertical:hover { background: $scroll_hover; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0 2px 2px 2px; }
QScrollBar::handle:horizontal { background: $scroll; border-radius: 3px; min-width: 28px; margin: 2px 0; }
QScrollBar::handle:horizontal:hover { background: $scroll_hover; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; background: transparent; border: none; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QWidget#sidebar QScrollBar:vertical { width: 6px; }
QWidget#sidebar QScrollBar::handle:vertical { background: $sidebar_border; margin: 0 1px; }
QWidget#sidebar QScrollBar::handle:vertical:hover { background: $accent_line; }

QStatusBar { background: $surface; border-top: 1px solid $border; color: $text_faint; }
QStatusBar::item { border: none; }
QStatusBar QLabel { color: $text_faint; font-size: 11px; padding: 0 3px; }

QToolTip {
    background: $tooltip_bg; color: $tooltip_text; border: 1px solid $accent_line;
    border-radius: 6px; padding: 5px 8px; font-size: 11px;
}

QTextBrowser, QTextEdit, QPlainTextEdit {
    background: $surface; color: $text; border: 1px solid $border; border-radius: 10px;
    padding: 8px; selection-background-color: $accent_soft; selection-color: $accent_strong;
}
QPlainTextEdit#importSource { font-family: $mono; font-size: 12px; }
QPlainTextEdit#importErrors { background: $danger_soft; color: $danger; border-color: $danger_line; }
QDialogButtonBox QPushButton { min-width: 78px; }
QMessageBox { background: $surface; }
QMessageBox QLabel { color: $text; font-size: 13px; }
QMessageBox QPushButton { min-width: 82px; }
"""
)


def stylesheet(colors: Palette) -> str:
    return _QSS.substitute(asdict(colors))


def apply_theme(app: QApplication, dark: bool) -> Palette:
    """Apply palette + QSS and remember the active tokens for new widgets."""

    global _CURRENT

    colors = palette_for(dark)
    _CURRENT = colors
    app.setPalette(qpalette(colors))
    app.setStyleSheet(stylesheet(colors))
    return colors


def theme_style(dark: bool = False) -> str:
    """Backwards-compatible helper used by tests and older call sites."""

    return stylesheet(palette_for(dark))


STYLE = stylesheet(LIGHT)
