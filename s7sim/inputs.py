"""Consistent native editors with visible controls in both themes."""
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPainter, QPalette, QPen
from PySide6.QtWidgets import QComboBox, QSpinBox, QStyle, QStyleOptionSpinBox


def chevron(painter, center, up=False):
    x, y = center.x(), center.y()
    direction = -1 if up else 1
    painter.drawLine(QPointF(x - 3, y - direction), QPointF(x, y + 2 * direction))
    painter.drawLine(QPointF(x, y + 2 * direction), QPointF(x + 3, y - direction))


class ChoiceBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event):  # noqa: N802
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()

    def paintEvent(self, event):  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(self.palette().color(QPalette.ColorRole.Text), 1.4))
        chevron(painter, QPointF(self.width() - 16, self.height() / 2 - 1))


class NumberBox(QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.lineEdit().setTextMargins(10, 0, 0, 0)

    def wheelEvent(self, event):  # noqa: N802
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()

    def paintEvent(self, event):  # noqa: N802
        super().paintEvent(event)
        option = QStyleOptionSpinBox()
        self.initStyleOption(option)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for control, step, up in (
            (QStyle.SubControl.SC_SpinBoxUp, self.StepEnabledFlag.StepUpEnabled, True),
            (QStyle.SubControl.SC_SpinBoxDown, self.StepEnabledFlag.StepDownEnabled, False),
        ):
            rect = self.style().subControlRect(QStyle.ComplexControl.CC_SpinBox, option, control, self)
            group = QPalette.ColorGroup.Active if self.isEnabled() and self.stepEnabled() & step else QPalette.ColorGroup.Disabled
            painter.setPen(QPen(self.palette().color(group, QPalette.ColorRole.Text), 1.2))
            chevron(painter, rect.center(), up)
