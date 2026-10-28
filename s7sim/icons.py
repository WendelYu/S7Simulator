"""Tiny hand-drawn vector icon set.

Icons are painted on a 64×64 design grid.  Rendering them in code keeps the
application free of external image assets while still giving crisp, theme-aware
pixmaps on high-DPI displays.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap,
)


def paint_glyph(painter: QPainter, name: str, rect: QRectF, color: QColor, weight: float | None = None) -> None:
    """Draw ``name`` into a square rect using a 64-unit design grid."""

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    side = min(rect.width(), rect.height())
    if side <= 0:
        painter.restore()
        return
    painter.translate(rect.center())
    painter.translate(-side / 2.0, -side / 2.0)
    painter.scale(side / 64.0, side / 64.0)

    c = QColor(color)
    pen = QPen(c)
    pen.setWidthF(weight if weight is not None else 5.1)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    def line(x1: float, y1: float, x2: float, y2: float) -> None:
        painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    if name == "play":
        path = QPainterPath(QPointF(22, 13))
        path.lineTo(52, 32)
        path.lineTo(22, 51)
        path.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(c)
        painter.drawPath(path)
    elif name == "stop":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(c)
        painter.drawRoundedRect(QRectF(19, 19, 26, 26), 5, 5)
    elif name == "plus":
        line(32, 14, 32, 50)
        line(14, 32, 50, 32)
    elif name == "x":
        line(19, 19, 45, 45)
        line(45, 19, 19, 45)
    elif name == "check":
        path = QPainterPath(QPointF(13, 34))
        path.lineTo(26, 47)
        path.lineTo(51, 18)
        painter.drawPath(path)
    elif name == "chevron-down":
        path = QPainterPath(QPointF(18, 25))
        path.lineTo(32, 39)
        path.lineTo(46, 25)
        painter.drawPath(path)
    elif name == "chevron-right":
        path = QPainterPath(QPointF(25, 18))
        path.lineTo(39, 32)
        path.lineTo(25, 46)
        painter.drawPath(path)
    elif name == "alert":
        path = QPainterPath(QPointF(32, 9))
        path.lineTo(57, 53)
        path.lineTo(7, 53)
        path.closeSubpath()
        painter.drawPath(path)
        line(32, 24, 32, 37)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(c)
        painter.drawEllipse(QPointF(32, 45), 3.2, 3.2)
    elif name == "info":
        painter.drawEllipse(QPointF(32, 32), 23, 23)
        line(32, 29, 32, 45)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(c)
        painter.drawEllipse(QPointF(32, 19), 3.1, 3.1)
    elif name == "search":
        painter.drawEllipse(QRectF(11, 11, 31, 31))
        line(39, 39, 53, 53)
    elif name == "folder":
        path = QPainterPath(QPointF(8, 19))
        path.lineTo(23, 19)
        path.lineTo(30, 27)
        path.lineTo(56, 27)
        path.lineTo(56, 49)
        path.lineTo(8, 49)
        path.closeSubpath()
        painter.drawPath(path)
        line(8, 35, 56, 35)
    elif name == "save":
        painter.drawRoundedRect(QRectF(12, 11, 40, 42), 4, 4)
        painter.drawRoundedRect(QRectF(21, 11, 22, 14), 2, 2)
        painter.drawRoundedRect(QRectF(20, 40, 24, 13), 2, 2)
    elif name == "sun":
        painter.drawEllipse(QPointF(32, 32), 10, 10)
        import math

        for i in range(8):
            angle = i * math.pi / 4
            x1 = 32 + math.cos(angle) * 17
            y1 = 32 + math.sin(angle) * 17
            x2 = 32 + math.cos(angle) * 25
            y2 = 32 + math.sin(angle) * 25
            line(x1, y1, x2, y2)
    elif name == "moon":
        path = QPainterPath(QPointF(42, 9))
        path.cubicTo(19, 14, 18, 50, 42, 55)
        path.cubicTo(30, 45, 30, 20, 42, 9)
        path.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(c)
        painter.drawPath(path)
    elif name == "settings":
        painter.drawEllipse(QPointF(32, 32), 9, 9)
        import math

        for i in range(8):
            angle = i * math.pi / 4 + math.pi / 8
            x1 = 32 + math.cos(angle) * 18
            y1 = 32 + math.sin(angle) * 18
            x2 = 32 + math.cos(angle) * 25
            y2 = 32 + math.sin(angle) * 25
            line(x1, y1, x2, y2)
    elif name == "gauge":
        path = QPainterPath()
        path.arcMoveTo(QRectF(11, 15, 42, 42), 200)
        path.arcTo(QRectF(11, 15, 42, 42), 200, -220)
        painter.drawPath(path)
        line(32, 37, 44, 24)
        painter.setBrush(c)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(32, 37), 3.2, 3.2)
    elif name == "link":
        painter.save()
        painter.translate(32, 32)
        painter.rotate(-45)
        painter.drawRoundedRect(QRectF(-25, -9, 25, 18), 9, 9)
        painter.drawRoundedRect(QRectF(0, -9, 25, 18), 9, 9)
        painter.restore()
        line(24, 32, 40, 32)
    elif name == "database":
        painter.drawEllipse(QRectF(13, 10, 38, 13))
        line(13, 16, 13, 46)
        line(51, 16, 51, 46)
        path = QPainterPath()
        path.arcMoveTo(QRectF(13, 40, 38, 13), 180)
        path.arcTo(QRectF(13, 40, 38, 13), 180, 180)
        painter.drawPath(path)
        for y in (25, 35):
            path = QPainterPath()
            path.arcMoveTo(QRectF(13, y, 38, 12), 180)
            path.arcTo(QRectF(13, y, 38, 12), 180, 180)
            painter.drawPath(path)
    elif name == "activity":
        path = QPainterPath(QPointF(7, 39))
        path.lineTo(17, 39)
        path.lineTo(23, 20)
        path.lineTo(33, 49)
        path.lineTo(40, 31)
        path.lineTo(57, 31)
        painter.drawPath(path)
    elif name == "edit":
        path = QPainterPath(QPointF(15, 49))
        path.lineTo(18, 37)
        path.lineTo(42, 13)
        path.lineTo(51, 22)
        path.lineTo(27, 46)
        path.closeSubpath()
        painter.drawPath(path)
        line(37, 18, 46, 27)
    elif name == "trash":
        line(11, 18, 53, 18)
        line(25, 12, 39, 12)
        path = QPainterPath(QPointF(17, 18))
        path.lineTo(20, 53)
        path.lineTo(44, 53)
        path.lineTo(47, 18)
        painter.drawPath(path)
        line(27, 26, 27, 45)
        line(37, 26, 37, 45)
    elif name == "copy":
        painter.drawRoundedRect(QRectF(12, 14, 28, 32), 3, 3)
        painter.drawRoundedRect(QRectF(24, 24, 28, 32), 3, 3)
    elif name == "cpu":
        painter.drawRoundedRect(QRectF(17, 17, 30, 30), 4, 4)
        painter.drawRoundedRect(QRectF(26, 26, 12, 12), 2, 2)
        for pos in (24, 32, 40):
            line(pos, 17, pos, 8)
            line(pos, 47, pos, 56)
            line(8, pos, 17, pos)
            line(47, pos, 56, pos)
    elif name == "bolt":
        path = QPainterPath(QPointF(37, 6))
        path.lineTo(14, 36)
        path.lineTo(29, 36)
        path.lineTo(24, 58)
        path.lineTo(50, 26)
        path.lineTo(34, 26)
        path.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(c)
        painter.drawPath(path)
    elif name == "terminal":
        painter.drawRoundedRect(QRectF(8, 12, 48, 40), 4, 4)
        path = QPainterPath(QPointF(17, 24))
        path.lineTo(27, 32)
        path.lineTo(17, 40)
        painter.drawPath(path)
        line(34, 40, 46, 40)
    elif name == "download":
        line(32, 11, 32, 40)
        path = QPainterPath(QPointF(19, 29))
        path.lineTo(32, 42)
        path.lineTo(45, 29)
        painter.drawPath(path)
        path = QPainterPath(QPointF(13, 47))
        path.lineTo(13, 54)
        path.lineTo(51, 54)
        path.lineTo(51, 47)
        painter.drawPath(path)
    elif name == "filter":
        path = QPainterPath(QPointF(9, 13))
        path.lineTo(55, 13)
        path.lineTo(38, 33)
        path.lineTo(38, 50)
        path.lineTo(26, 55)
        path.lineTo(26, 33)
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "power":
        path = QPainterPath()
        path.arcMoveTo(QRectF(12, 14, 40, 40), 55)
        path.arcTo(QRectF(12, 14, 40, 40), 55, 250)
        painter.drawPath(path)
        line(32, 7, 32, 31)
    elif name == "columns":
        painter.drawRoundedRect(QRectF(9, 13, 46, 38), 4, 4)
        line(25, 13, 25, 51)
        line(40, 13, 40, 51)
    elif name == "dots":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(c)
        for x in (19, 32, 45):
            painter.drawEllipse(QPointF(x, 32), 3.4, 3.4)
    elif name == "dot":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(c)
        painter.drawEllipse(QPointF(32, 32), 11, 11)
    elif name == "refresh":
        path = QPainterPath()
        path.arcMoveTo(QRectF(12, 12, 40, 40), 45)
        path.arcTo(QRectF(12, 12, 40, 40), 45, 280)
        painter.drawPath(path)
        path = QPainterPath(QPointF(44, 8))
        path.lineTo(52, 22)
        path.lineTo(37, 25)
        painter.drawPath(path)
    elif name == "book":
        path = QPainterPath(QPointF(32, 16))
        path.cubicTo(24, 10, 14, 12, 9, 15)
        path.lineTo(9, 49)
        path.cubicTo(18, 46, 26, 47, 32, 53)
        path.cubicTo(38, 47, 46, 46, 55, 49)
        path.lineTo(55, 15)
        path.cubicTo(50, 12, 40, 10, 32, 16)
        painter.drawPath(path)
        line(32, 16, 32, 52)
    elif name == "sliders":
        for y, knob in ((19, 42), (32, 25), (45, 36)):
            line(10, y, 54, y)
            painter.setBrush(c)
            painter.setPen(QPen(c, 5.0))
            painter.drawEllipse(QPointF(knob, y), 4, 4)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
    else:
        painter.drawEllipse(QPointF(32, 32), 22, 22)

    painter.restore()


def make_pixmap(name: str, color: str | QColor, size: int = 18) -> QPixmap:
    """Return a Retina-friendly pixmap at ``size`` logical pixels."""

    ratio = 2
    pm = QPixmap(size * ratio, size * ratio)
    pm.setDevicePixelRatio(ratio)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    paint_glyph(painter, name, QRectF(0, 0, size, size), QColor(color))
    painter.end()
    return pm


def make_icon(name: str, color: str | QColor, size: int = 18, faded: str | QColor | None = None) -> QIcon:
    c = QColor(color)
    icon = QIcon(make_pixmap(name, c, 32))
    muted = QColor(faded) if faded is not None else QColor(c)
    muted.setAlpha(95)
    icon.addPixmap(make_pixmap(name, muted, 32), QIcon.Mode.Disabled, QIcon.State.Off)
    return icon
