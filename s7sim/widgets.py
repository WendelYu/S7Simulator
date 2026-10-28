"""Reusable, theme-aware UI components for S7 Studio.

Everything here is painted with QPainter instead of leaning on platform widgets;
that keeps the workbench consistent on macOS and Windows and lets us add small
movements (gliding selection, pulsing status, animated values) without fighting
native styles.
"""

from __future__ import annotations

import math
import time
from collections import deque

from PySide6.QtCore import (
    Property, QEasingCurve, QEvent, QObject, QPoint, QPointF, QPropertyAnimation,
    QRectF, QSize, Qt, QTimer, QVariantAnimation, Signal,
)
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontMetrics, QLinearGradient, QPainter,
    QPainterPath, QPen, QPixmap, QRadialGradient,
)
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSizePolicy, QStyle, QStyledItemDelegate,
    QStyleOptionViewItem, QTabBar, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QWidget,
)

from . import icons, motion
from .theme import (
    LIGHT, MONO_FONT, Palette, STYLE, current, palette_for, theme_style,
)

ACCENT = LIGHT.accent

TONE_KEYS = ("accent", "ok", "warn", "danger", "info", "muted", "text")


def tone_color(colors: Palette, key: str) -> str:
    mapping = {
        "accent": colors.accent,
        "ok": colors.ok,
        "warn": colors.warn,
        "danger": colors.danger,
        "info": colors.info,
        "muted": colors.text_faint,
        "text": colors.text,
    }
    return mapping.get(key, key)


def _font(base: QFont, px: float, weight=QFont.Weight.Normal, mono: bool = False) -> QFont:
    f = QFont(base)
    f.setPixelSize(max(1, int(round(px))))
    f.setWeight(weight)
    if mono:
        f.setFamilies(["SF Mono", "Menlo", "Cascadia Mono", "Consolas", "Liberation Mono"])
    return f


def _elide(painter: QPainter, text: str, rect: QRectF, color: QColor, font: QFont,
           align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter) -> None:
    painter.setFont(font)
    painter.setPen(color)
    fm = QFontMetrics(font)
    clipped = fm.elidedText(str(text), Qt.TextElideMode.ElideRight, max(1, int(rect.width())))
    painter.drawText(rect, align, clipped)


def _chip(painter: QPainter, rect: QRectF, bg: QColor, border: QColor | None, text: str,
          color: QColor, font: QFont, radius: float = 6) -> None:
    painter.setPen(QPen(border, 1) if border is not None else Qt.PenStyle.NoPen)
    painter.setBrush(bg)
    painter.drawRoundedRect(rect, radius, radius)
    _elide(painter, text, rect.adjusted(7, 0, -7, 0), color, font,
           Qt.AlignmentFlag.AlignCenter)


def _discard_anim(owner, attr):
    """Stop and release a stored animation before it is replaced."""
    anim = getattr(owner, attr, None)
    if anim is None:
        return
    try:
        anim.stop()
        anim.deleteLater()
    except RuntimeError:
        pass
    setattr(owner, attr, None)


class BrandMark(QWidget):
    def __init__(self, size: int = 38, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.colors = current()

    def apply_theme(self, colors: Palette) -> None:
        self.colors = colors
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        c = self.colors
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0, QColor(c.accent_grad_a))
        grad.setColorAt(1, QColor(c.accent_grad_b))
        p.setPen(QPen(QColor(c.accent_line), 1))
        p.setBrush(grad)
        p.drawRoundedRect(rect, 11, 11)

        # a soft top highlight keeps the tile from looking flat
        hl = QLinearGradient(0, 0, 0, self.height() * 0.7)
        top = QColor(255, 255, 255, 44)
        bottom = QColor(255, 255, 255, 0)
        hl.setColorAt(0, top)
        hl.setColorAt(1, bottom)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(hl)
        p.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 10, 10)

        inset = self.width() * 0.22
        icons.paint_glyph(
            p, "bolt",
            QRectF(inset, inset * 0.8, self.width() - inset * 2, self.height() - inset * 1.9),
            QColor(c.on_accent), weight=4.4,
        )
        p.end()


class Sidebar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.colors = current()

    def apply_theme(self, colors: Palette) -> None:
        self.colors = colors
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        c = self.colors
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QLinearGradient(0, 0, 0, self.height())
        bg.setColorAt(0, QColor(c.sidebar_alt))
        bg.setColorAt(0.55, QColor(c.sidebar))
        bg.setColorAt(1, QColor(c.sidebar_alt))
        p.fillRect(self.rect(), bg)

        glow = QColor(c.accent)
        glow.setAlpha(30)
        radial = QRadialGradient(QPointF(self.width() * 0.88, 58), 230)
        radial.setColorAt(0, glow)
        fade = QColor(c.accent)
        fade.setAlpha(0)
        radial.setColorAt(1, fade)
        p.fillRect(self.rect(), QBrush(radial))

        glow2 = QColor(c.accent)
        glow2.setAlpha(14)
        radial2 = QRadialGradient(QPointF(self.width() * 0.1, self.height() - 40), 250)
        radial2.setColorAt(0, glow2)
        radial2.setColorAt(1, fade)
        p.fillRect(self.rect(), QBrush(radial2))

        p.setPen(QPen(QColor(c.sidebar_border), 1))
        p.drawLine(self.width() - 1, 0, self.width() - 1, self.height())

        top = QLinearGradient(0, 0, self.width() * 0.75, 0)
        a = QColor(c.accent)
        a.setAlpha(120)
        top.setColorAt(0, a)
        top.setColorAt(1, QColor(c.accent).darker(100))
        p.setPen(QPen(QBrush(top), 2))
        p.drawLine(0, 1, int(self.width() * 0.7), 1)
        p.end()


class ThemeToggle(QWidget):
    toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(58, 30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("切换浅色 / 深色主题")
        self.colors = current()
        self._dark = self.colors.name == "dark"
        self._pos = 1.0 if self._dark else 0.0
        self._anim: QPropertyAnimation | None = None

    def _get_knob_pos(self) -> float:
        return self._pos

    def _set_knob_pos(self, value: float) -> None:
        self._pos = float(value)
        self.update()

    # Do not call this property "pos": QWidget already owns a QPoint `pos`,
    # and QPropertyAnimation would then move the widget to its parent origin.
    knob_pos = Property(float, _get_knob_pos, _set_knob_pos)

    def set_dark(self, dark: bool, animate: bool = False) -> None:
        target = 1.0 if dark else 0.0
        self._dark = bool(dark)
        if abs(self._pos - target) < 0.001:
            return
        if animate and motion.enabled():
            _discard_anim(self, "_anim")
            anim = QPropertyAnimation(self, b"knob_pos", self)
            anim.setDuration(260)
            anim.setStartValue(self._pos)
            anim.setEndValue(target)
            anim.setEasingCurve(QEasingCurve.Type.OutBack)
            anim.start()
            self._anim = anim
        else:
            self._pos = target
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            new_value = not self._dark
            self.set_dark(new_value, animate=True)
            self.toggled.emit(new_value)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def apply_theme(self, colors: Palette) -> None:
        self.colors = colors
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        c = self.colors
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        p.setPen(QPen(QColor(c.border), 1))
        p.setBrush(QColor(c.surface_alt))
        p.drawRoundedRect(track, 15, 15)

        sun_color = QColor(c.text_faint) if self._pos > 0.5 else QColor(c.warn)
        moon_color = QColor(c.accent) if self._pos > 0.5 else QColor(c.text_faint)
        icons.paint_glyph(p, "sun", QRectF(7, 8, 14, 14), sun_color)
        icons.paint_glyph(p, "moon", QRectF(self.width() - 21, 8, 14, 14), moon_color)

        knob = 24.0
        x = 3.0 + self._pos * (self.width() - knob - 6.0)
        knob_rect = QRectF(x, 3.0, knob, knob)
        shadow = QColor(c.shadow)
        shadow.setAlpha(34)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(shadow)
        p.drawEllipse(knob_rect.adjusted(0, 1.2, 0, 1.2))
        p.setPen(QPen(QColor(c.border_strong), 1))
        p.setBrush(QColor(c.surface))
        p.drawEllipse(knob_rect)

        glyph = "moon" if self._pos > 0.5 else "sun"
        glyph_color = QColor(c.accent_strong) if self._pos > 0.5 else QColor(c.warn)
        icons.paint_glyph(p, glyph, knob_rect.adjusted(5, 5, -5, -5), glyph_color)
        p.end()


class StatusPill(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.colors = current()
        self._state = "OFFLINE"
        self._tone_key = "muted"
        self._pulse = 0.0
        self._pulse_anim: QVariantAnimation | None = None
        self.setFixedHeight(30)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.set_state("OFFLINE")

    def _get_pulse(self) -> float:
        return self._pulse

    def _set_pulse(self, value: float) -> None:
        self._pulse = float(value)
        self.update()

    pulse = Property(float, _get_pulse, _set_pulse)

    def set_state(self, state: str) -> None:
        state = state or "OFFLINE"
        if state == "RUN":
            tone = "ok"
        elif "STOP" in state:
            tone = "warn"
        elif state.startswith("CPU"):
            tone = "info"
        else:
            tone = "muted"
        self._state = state
        self._tone_key = tone
        fm = QFontMetrics(_font(self.font(), 11, QFont.Weight.DemiBold))
        width = 34 + fm.horizontalAdvance(state) + 14
        self.setFixedWidth(max(92, width))
        self._sync_pulse()
        self.update()

    def _sync_pulse(self) -> None:
        running = self._state == "RUN" and motion.enabled()
        if running and self._pulse_anim is None:
            anim = QVariantAnimation(self)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setDuration(1900)
            anim.setLoopCount(-1)
            anim.setEasingCurve(QEasingCurve.Type.InOutSine)
            anim.valueChanged.connect(self._set_pulse)
            anim.start()
            self._pulse_anim = anim
        elif not running and self._pulse_anim is not None:
            self._pulse_anim.stop()
            self._pulse_anim.deleteLater()
            self._pulse_anim = None
            self._pulse = 0.0
            self.update()

    def apply_theme(self, colors: Palette) -> None:
        self.colors = colors
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        c = self.colors
        tone = QColor(tone_color(c, self._tone_key))
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)

        bg = QColor(tone)
        bg.setAlpha(40 if c.name == "dark" else 26)
        border = QColor(tone)
        border.setAlpha(78 if c.name == "dark" else 62)
        p.setPen(QPen(border, 1))
        p.setBrush(bg)
        p.drawRoundedRect(rect, 15, 15)

        cy = rect.center().y()
        dot = QPointF(16, cy)
        if self._state == "RUN":
            ring = QColor(tone)
            ring.setAlpha(int(70 * (1 - self._pulse)))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(ring)
            radius = 4.0 + self._pulse * 5.0
            p.drawEllipse(dot, radius, radius)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(tone)
        p.drawEllipse(dot, 3.4, 3.4)

        text_color = QColor(c.text_muted) if self._tone_key == "muted" else tone
        font = _font(self.font(), 11, QFont.Weight.DemiBold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.7)
        _elide(p, self._state, QRectF(26, 0, self.width() - 34, self.height()), text_color, font,
               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        p.end()


class IconTile(QWidget):
    def __init__(self, glyph: str = "activity", tone: str = "accent", size: int = 38,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.glyph = glyph
        self.tone_key = tone
        self.colors = current()

    def set_icon(self, glyph: str, tone: str | None = None) -> None:
        self.glyph = glyph
        if tone is not None:
            self.tone_key = tone
        self.update()

    def apply_theme(self, colors: Palette) -> None:
        self.colors = colors
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        c = self.colors
        tone = QColor(tone_color(c, self.tone_key))
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        bg = QColor(tone)
        bg.setAlpha(34 if c.name == "dark" else 24)
        border = QColor(tone)
        border.setAlpha(54 if c.name == "dark" else 42)
        p.setPen(QPen(border, 1))
        p.setBrush(bg)
        p.drawRoundedRect(rect, self.width() * 0.27, self.width() * 0.27)
        inset = self.width() * 0.26
        icons.paint_glyph(p, self.glyph, QRectF(inset, inset, self.width() - inset * 2,
                                                self.height() - inset * 2), tone)
        p.end()


class StatValue(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.colors = current()
        self._text = ""
        self._base = QColor(self.colors.text)
        self._flash = 0.0
        self._anim: QPropertyAnimation | None = None
        self.setFixedHeight(36)
        self.setMinimumWidth(40)

    def _get_flash(self) -> float:
        return self._flash

    def _set_flash(self, value: float) -> None:
        self._flash = float(value)
        self.update()

    flash = Property(float, _get_flash, _set_flash)

    def text(self) -> str:
        return self._text

    def set_value(self, text: str) -> None:
        text = str(text)
        if text == self._text:
            return
        self._text = text
        self.setAccessibleName(text)
        if motion.enabled():
            _discard_anim(self, "_anim")
            anim = QPropertyAnimation(self, b"flash", self)
            anim.setDuration(560)
            anim.setStartValue(1.0)
            anim.setEndValue(0.0)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.start()
            self._anim = anim
        self.update()

    def set_tone(self, color: str) -> None:
        self._base = QColor(color)
        self.update()

    def apply_theme(self, colors: Palette) -> None:
        self.colors = colors
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        c = self.colors
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = _font(self.font(), 26, QFont.Weight.Bold)
        color = motion.lerp_color(self._base, QColor(c.accent_hover), self._flash * 0.8)
        _elide(p, self._text, QRectF(0, 0, self.width(), self.height()), color, font,
               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        p.end()


class StatCard(QFrame):
    def __init__(self, caption: str, value: str = "", detail: str = "",
                 icon: str = "activity", tone: str = "muted",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.colors = current()
        self.tone_key = tone
        self.setMinimumHeight(116)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 13)
        layout.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(8)
        self.caption = QLabel(caption)
        self.caption.setObjectName("cardCaption")
        top.addWidget(self.caption)
        top.addStretch(1)
        self.icon = IconTile(icon, tone, 36)
        top.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(top)

        self.value = StatValue()
        self.value.set_value(value)
        layout.addWidget(self.value)

        self.detail = QLabel(detail)
        self.detail.setObjectName("cardDetail")
        self.detail.setWordWrap(False)
        layout.addWidget(self.detail)

        self._hover = motion.HoverShadow(
            self, self.colors.shadow, 32,
            rest_blur=14, hover_blur=28, rest_dy=2, hover_dy=6,
        )
        self.set_tone(tone)

    def set_value(self, value: str) -> None:
        self.value.set_value(value)

    def set_detail(self, detail: str) -> None:
        if self.detail.text() != detail:
            self.detail.setText(detail)

    def set_tone(self, tone: str) -> None:
        self.tone_key = tone
        self.value.set_tone(tone_color(self.colors, tone))
        self.icon.set_icon(self.icon.glyph, tone)
        self.update()

    def set_icon(self, glyph: str, tone: str | None = None) -> None:
        self.icon.set_icon(glyph, tone or self.tone_key)

    def apply_theme(self, colors: Palette) -> None:
        self.colors = colors
        self.icon.apply_theme(colors)
        self.value.apply_theme(colors)
        self.value.set_tone(tone_color(colors, self.tone_key))
        self._hover.set_color(colors.shadow, 36 if colors.name == "dark" else 30)
        self.update()


class MetricValue(QWidget):
    """The big monospaced live value in the inspector."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.colors = current()
        self._text = "—"
        self._error = False
        self._flash = 0.0
        self._anim: QPropertyAnimation | None = None
        self.setFixedHeight(54)
        self.setMinimumWidth(120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAccessibleName("当前值")

    def _get_flash(self) -> float:
        return self._flash

    def _set_flash(self, value: float) -> None:
        self._flash = float(value)
        self.update()

    flash = Property(float, _get_flash, _set_flash)

    def text(self) -> str:
        return self._text

    def set_value(self, text: str, error: bool = False) -> None:
        text = str(text)
        changed = text != self._text
        self._text = text
        self._error = error
        self.setAccessibleName(text)
        if changed and motion.enabled():
            _discard_anim(self, "_anim")
            anim = QPropertyAnimation(self, b"flash", self)
            anim.setDuration(380)
            anim.setStartValue(1.0)
            anim.setEndValue(0.0)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.start()
            self._anim = anim
        self.update()

    def apply_theme(self, colors: Palette) -> None:
        self.colors = colors
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        c = self.colors
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        n = len(self._text)
        if n > 60:
            px = 15
        elif n > 40:
            px = 18
        elif n > 26:
            px = 22
        else:
            px = 29
        font = _font(self.font(), px, QFont.Weight.DemiBold, mono=True)
        base = QColor(c.danger if self._error else c.accent)
        hot = QColor(c.danger) if self._error else QColor(c.accent_hover)
        color = motion.lerp_color(base, hot, self._flash)

        scale = 1.0 + 0.025 * self._flash
        p.save()
        p.translate(1.0, self.height() / 2.0)
        p.scale(scale, scale)
        _elide(p, self._text, QRectF(0, -self.height() / 2.0, self.width() - 2, self.height()),
               color, font, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        p.restore()
        p.end()


class Sparkline(QWidget):
    """Live trend plot with a smooth curve and hover readout."""

    MAX_POINTS = 120

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.colors = current()
        self.values: deque[float] = deque(maxlen=self.MAX_POINTS)
        self._discrete = False
        self._reveal = 1.0
        self._reveal_anim: QPropertyAnimation | None = None
        self._hover = -1
        self._plot = QRectF()
        self._points: list[QPointF] = []
        self.setFixedHeight(112)
        self.setMinimumWidth(180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self.setToolTip(
            "最近 120 个界面采样点；约 30 秒。数组显示第一个元素，BOOL 以 ON/OFF 阶梯显示。\n"
            "将鼠标移到曲线上可查看具体采样值。"
        )

    def _get_reveal(self) -> float:
        return self._reveal

    def _set_reveal(self, value: float) -> None:
        self._reveal = float(value)
        self.update()

    reveal = Property(float, _get_reveal, _set_reveal)

    def clear(self) -> None:
        self.values.clear()
        self._discrete = False
        self._hover = -1
        if self._reveal_anim is not None:
            self._reveal_anim.stop()
            self._reveal_anim.deleteLater()
            self._reveal_anim = None
        self._reveal = 0.0
        self.update()

    def append(self, value) -> None:
        if isinstance(value, (list, tuple)):
            value = value[0] if value else None
        if isinstance(value, bool):
            self._discrete = True
            value = 1.0 if value else 0.0
        elif isinstance(value, (int, float)):
            if self._discrete:
                self.values.clear()
                self._discrete = False
            value = float(value)
        else:
            return
        if not math.isfinite(float(value)):
            return
        self.values.append(float(value))
        if len(self.values) == 1 and motion.enabled():
            _discard_anim(self, "_reveal_anim")
            anim = QPropertyAnimation(self, b"reveal", self)
            anim.setDuration(460)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.start()
            self._reveal_anim = anim
        self.update()

    def apply_theme(self, colors: Palette) -> None:
        self.colors = colors
        self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if len(self.values) >= 2 and self._plot.contains(event.position()):
            spacing = self._plot.width() / max(1, len(self._points) - 1)
            idx = round((event.position().x() - self._plot.left()) / max(0.001, spacing))
            self._hover = max(0, min(len(self._points) - 1, int(idx)))
            self.update()
        elif self._hover != -1:
            self._hover = -1
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        if self._hover != -1:
            self._hover = -1
            self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        c = self.colors
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        outer = QRectF(0.5, 0.5, w - 1, h - 1)
        p.setPen(QPen(QColor(c.border), 1))
        p.setBrush(QColor(c.surface_alt))
        p.drawRoundedRect(outer, 10, 10)

        plot = QRectF(13, 22, max(40.0, w - 66), max(40.0, h - 52))
        self._plot = plot

        # grid
        grid_pen = QPen(QColor(c.chart_grid), 1, Qt.PenStyle.DashLine)
        grid_pen.setDashPattern([2, 4])
        p.setPen(grid_pen)
        for i in range(3):
            y = plot.top() + plot.height() * i / 2.0
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))

        if len(self.values) < 2:
            p.setPen(QPen(QColor(c.accent_line), 1, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(plot.left(), plot.center().y()),
                       QPointF(plot.right(), plot.center().y()))
            label = "选择变量以查看实时趋势" if self._hover == -1 else ""
            _elide(p, label, QRectF(plot.left(), plot.top(), plot.width(), plot.height()),
                   QColor(c.text_faint), _font(self.font(), 10.5), Qt.AlignmentFlag.AlignCenter)
            self._draw_labels(p, plot, None, None)
            p.end()
            return

        values = list(self.values)
        if self._discrete:
            lo, hi = 0.0, 1.0
        else:
            lo, hi = min(values), max(values)
            if hi - lo < 1e-9:
                hi += 1.0
                lo -= 1.0
            pad = (hi - lo) * 0.14
            lo -= pad
            hi += pad

        n = len(values)
        spacing = plot.width() / max(1, n - 1) if n < self.MAX_POINTS else plot.width() / (self.MAX_POINTS - 1)
        points = [
            QPointF(plot.left() + i * spacing,
                    plot.bottom() - (v - lo) / (hi - lo) * plot.height())
            for i, v in enumerate(values)
        ]
        self._points = points

        line = QPainterPath(points[0])
        for i in range(1, len(points)):
            if self._discrete:
                line.lineTo(QPointF(points[i].x(), points[i - 1].y()))
                line.lineTo(points[i])
            else:
                a, b = points[i - 1], points[i]
                mid = (a.x() + b.x()) / 2.0
                line.cubicTo(QPointF(mid, a.y()), QPointF(mid, b.y()), b)
        area = QPainterPath(line)
        area.lineTo(points[-1].x(), plot.bottom())
        area.lineTo(points[0].x(), plot.bottom())
        area.closeSubpath()

        p.save()
        p.setClipRect(QRectF(plot.left() - 3, plot.top() - 3,
                             (plot.width() + 6) * self._reveal, plot.height() + 12))
        fill = QLinearGradient(0, plot.top(), 0, plot.bottom())
        top = QColor(c.accent)
        top.setAlpha(70 if c.name == "dark" else 55)
        bottom = QColor(c.accent)
        bottom.setAlpha(0)
        fill.setColorAt(0, top)
        fill.setColorAt(1, bottom)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(fill)
        p.drawPath(area)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(c.accent), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                      Qt.PenJoinStyle.RoundJoin))
        p.drawPath(line)
        p.restore()

        last = points[-1]
        glow = QColor(c.accent)
        glow.setAlpha(50)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(last, 6.5, 6.5)
        p.setBrush(QColor(c.accent))
        p.drawEllipse(last, 3.2, 3.2)

        if self._hover >= 0 and self._hover < len(points):
            point = points[self._hover]
            hover_pen = QPen(QColor(c.accent), 1, Qt.PenStyle.DashLine)
            hover_pen.setDashPattern([2, 3])
            p.setPen(hover_pen)
            p.drawLine(QPointF(point.x(), plot.top()), QPointF(point.x(), plot.bottom()))
            ring = QColor(c.accent)
            ring.setAlpha(80)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(ring)
            p.drawEllipse(point, 6, 6)
            p.setBrush(QColor(c.surface))
            p.setPen(QPen(QColor(c.accent), 2))
            p.drawEllipse(point, 3.2, 3.2)
            self._draw_hover(p, plot, point, values[self._hover], len(values) - 1 - self._hover)

        self._draw_labels(p, plot, hi, lo)
        p.end()

    def _draw_labels(self, p: QPainter, plot: QRectF, hi: float | None, lo: float | None) -> None:
        c = self.colors
        font = _font(self.font(), 9)
        p.setFont(font)
        p.setPen(QColor(c.text_faint))
        p.drawText(QRectF(13, 4, 160, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   "实时趋势 · 30 秒")
        if hi is not None and lo is not None:
            top_text, bottom_text = (
                ("ON", "OFF") if self._discrete else (f"{hi:.3g}", f"{lo:.3g}")
            )
            p.drawText(QRectF(plot.right() + 7, plot.top() - 6, 42, 13),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, top_text)
            p.drawText(QRectF(plot.right() + 7, plot.bottom() - 7, 42, 13),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, bottom_text)
        p.drawText(QRectF(13, self.height() - 17, self.width() - 26, 12),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"{len(self.values)} / {self.MAX_POINTS} 采样")

    def _draw_hover(self, p: QPainter, plot: QRectF, point: QPointF, value: float, ago: int) -> None:
        c = self.colors
        value_font = _font(self.font(), 10.5, QFont.Weight.DemiBold, mono=True)
        sub_font = _font(self.font(), 9)
        fm_value = QFontMetrics(value_font)
        fm_sub = QFontMetrics(sub_font)
        main = ("ON" if value >= 0.5 else "OFF") if self._discrete else f"{value:.4g}"
        sub = f"{ago * 0.25:.1f} 秒前"
        box_w = max(72.0, max(fm_value.horizontalAdvance(main), fm_sub.horizontalAdvance(sub)) + 20)
        box_h = 40.0
        x = min(max(plot.left(), point.x() - box_w / 2), plot.right() - box_w)
        y = point.y() - box_h - 10
        if y < plot.top() + 2:
            y = point.y() + 10
        box = QRectF(x, y, box_w, box_h)
        shadow = QColor(c.shadow)
        shadow.setAlpha(40)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(shadow)
        p.drawRoundedRect(box.adjusted(0, 2, 0, 2), 7, 7)
        p.setBrush(QColor(c.surface))
        p.setPen(QPen(QColor(c.border_strong), 1))
        p.drawRoundedRect(box, 7, 7)
        p.setPen(QColor(c.accent))
        p.setFont(value_font)
        p.drawText(box.adjusted(9, 3, -5, -19), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, main)
        p.setPen(QColor(c.text_faint))
        p.setFont(sub_font)
        p.drawText(box.adjusted(9, 19, -5, -3), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, sub)


class UsageBar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.colors = current()
        self._ratio = 0.0
        self._target = 0.0
        self._anim = None
        self.setFixedSize(118, 6)
        self.setToolTip("数据块内存使用率")

    def _get_ratio(self) -> float:
        return self._ratio

    def _set_ratio(self, value: float) -> None:
        self._ratio = max(0.0, min(1.0, float(value)))
        self.update()

    ratio = Property(float, _get_ratio, _set_ratio)

    def set_usage(self, used: int, total: int) -> None:
        target = max(0.0, min(1.0, 0.0 if total <= 0 else used / total))
        if target == self._target and motion.enabled():
            return
        self._target = target
        _discard_anim(self, "_anim")
        if not motion.enabled():
            self._ratio = target
            self.update()
            return
        anim = QPropertyAnimation(self, b"ratio", self)
        anim.setDuration(420)
        anim.setStartValue(self._ratio)
        anim.setEndValue(min(1.0, target))
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._anim = anim

    def apply_theme(self, colors: Palette) -> None:
        self.colors = colors
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        c = self.colors
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(c.surface_press))
        p.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 3, 3)
        color = c.ok if self._ratio < 0.8 else (c.warn if self._ratio < 0.96 else c.danger)
        p.setBrush(QColor(color))
        p.drawRoundedRect(QRectF(0, 0, max(0.0, self.width() * self._ratio), self.height()), 3, 3)
        p.end()


# ---------------------------------------------------------------------------
# Navigation tree

ROLE_ID = int(Qt.ItemDataRole.UserRole)
ROLE_KIND = ROLE_ID + 1
ROLE_RUNNING = ROLE_ID + 2
ROLE_SUBTITLE = ROLE_ID + 3
ROLE_COUNT = ROLE_ID + 4
ROLE_DETAIL = ROLE_ID + 5


class NavDelegate(QStyledItemDelegate):
    def __init__(self, view: "NavTree") -> None:
        super().__init__(view)
        self.view = view
        self.colors = current()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:  # noqa: N802
        kind = index.data(ROLE_KIND)
        return QSize(150, 52 if kind == "plc" else 34)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        c = self.colors
        p = painter
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(option.rect)
        alpha = self.view.selection_alpha(index)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)

        if alpha > 0.01:
            bg = QColor(c.accent)
            bg.setAlphaF(0.10 * alpha + 0.01)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(bg)
            p.drawRoundedRect(r.adjusted(5, 3, -5, -3), 8, 8)
            bar = QColor(c.accent)
            bar.setAlphaF(alpha)
            p.setBrush(bar)
            p.drawRoundedRect(QRectF(r.left() + 6, r.top() + 9, 2.5, r.height() - 18), 1.2, 1.2)
        elif hover:
            bg = QColor(c.sidebar_button_hover)
            bg.setAlpha(150)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(bg)
            p.drawRoundedRect(r.adjusted(5, 3, -5, -3), 8, 8)

        kind = index.data(ROLE_KIND)
        if kind == "plc":
            running = bool(index.data(ROLE_RUNNING))
            dot = QPointF(r.left() + 17, r.center().y())
            ring = QColor(c.ok if running else c.sidebar_muted)
            ring.setAlpha(48)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(ring)
            p.drawEllipse(dot, 7, 7)
            p.setBrush(QColor(c.ok if running else c.sidebar_muted))
            p.drawEllipse(dot, 3.3, 3.3)

            name_rect = QRectF(r.left() + 30, r.top() + 9, max(30.0, r.width() - 40), 21)
            name = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
            font = _font(option.font, 12.5, QFont.Weight.DemiBold)
            _elide(p, name, name_rect, QColor(c.sidebar_text), font)
            sub = str(index.data(ROLE_SUBTITLE) or "")
            sub_font = _font(option.font, 9.5)
            _elide(p, sub, QRectF(r.left() + 30, r.top() + 28, r.width() - 40, 15),
                   QColor(c.sidebar_muted), sub_font)
        else:
            code = str(index.data(ROLE_SUBTITLE) or "")
            name = str(index.data(ROLE_DETAIL) or index.data(Qt.ItemDataRole.DisplayRole) or "")
            chip_font = _font(option.font, 9, QFont.Weight.DemiBold, mono=True)
            fm = QFontMetrics(chip_font)
            chip_w = fm.horizontalAdvance(code) + 18
            chip = QRectF(r.left() + 8, r.center().y() - 9.5, chip_w, 19)
            bg = QColor(c.accent)
            bg.setAlpha(32)
            border = QColor(c.accent)
            border.setAlpha(60)
            _chip(p, chip, bg, border, code, QColor(c.accent), chip_font, 5)

            count = index.data(ROLE_COUNT)
            font = _font(option.font, 10.5, QFont.Weight.Medium)
            name_width = QFontMetrics(font).horizontalAdvance(name)
            reserve = 46.0
            # Prefer a complete database name over the decorative count when
            # the sidebar is narrow; the count is still available in the tooltip.
            show_count = (
                count is not None
                and r.width() > 150
                and name_width <= r.width() - chip_w - 46
            )
            if not show_count:
                reserve = 16.0
            name_rect = QRectF(chip.right() + 8, r.top(),
                               max(20.0, r.width() - chip_w - reserve), r.height())
            color = QColor(c.sidebar_text)
            _elide(p, name, name_rect, color, font)

            if show_count:
                _elide(p, str(count), QRectF(r.right() - 30, r.top(), 20, r.height()),
                       QColor(c.sidebar_muted), _font(option.font, 8.5),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        p.restore()


class NavTree(QTreeWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("projectTree")
        self.setHeaderHidden(True)
        self.setIndentation(10)
        self.setRootIsDecorated(True)
        self.setAnimated(motion.enabled())
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setUniformRowHeights(False)
        self.setExpandsOnDoubleClick(True)
        self.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        self.colors = current()
        self._delegate = NavDelegate(self)
        self.setItemDelegate(self._delegate)
        self._progress = 1.0
        self._previous_item: QTreeWidgetItem | None = None
        self._anim: QPropertyAnimation | None = None
        self.currentItemChanged.connect(self._on_current)
        self.apply_theme(self.colors)

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() == Qt.Key.Key_Menu or (
            event.key() == Qt.Key.Key_F10 and event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            item = self.currentItem()
            point = self.visualItemRect(item).center() if item else QPoint(8, 8)
            self.customContextMenuRequested.emit(point)
            event.accept()
            return
        super().keyPressEvent(event)

    def _get_progress(self) -> float:
        return self._progress

    def _set_progress(self, value: float) -> None:
        self._progress = float(value)
        self.viewport().update()

    progress = Property(float, _get_progress, _set_progress)

    def _on_current(self, current: QTreeWidgetItem | None, previous: QTreeWidgetItem | None) -> None:
        _discard_anim(self, "_anim")
        self._previous_item = previous
        if current is None or not motion.enabled():
            self._previous_item = None
            self._progress = 1.0
            self.viewport().update()
            return
        self._progress = 0.0
        anim = QPropertyAnimation(self, b"progress", self)
        anim.setDuration(220)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        def done() -> None:
            self._previous_item = None
            self._progress = 1.0
            self.viewport().update()

        anim.finished.connect(done)
        anim.start()
        self._anim = anim

    def selection_alpha(self, index) -> float:
        current = self.currentItem()
        if current is None:
            return 0.0
        try:
            if self.indexFromItem(current) == index:
                return self._progress
            if self._previous_item is not None:
                if self.indexFromItem(self._previous_item) == index:
                    return max(0.0, 1.0 - self._progress)
        except (RuntimeError, TypeError):
            self._previous_item = None
        return 0.0

    def snap_selection(self) -> None:
        if self._anim is not None:
            self._anim.stop()
            self._anim = None
        self._previous_item = None
        self._progress = 1.0
        self.viewport().update()

    def apply_theme(self, colors: Palette) -> None:
        self.colors = colors
        self._delegate.colors = colors
        pal = self.palette()
        pal.setColor(pal.ColorRole.WindowText, QColor(colors.sidebar_text))
        pal.setColor(pal.ColorRole.Text, QColor(colors.sidebar_text))
        pal.setColor(pal.ColorRole.ButtonText, QColor(colors.sidebar_muted))
        pal.setColor(pal.ColorRole.Highlight, QColor(colors.accent))
        pal.setColor(pal.ColorRole.HighlightedText, QColor(colors.sidebar_text))
        pal.setColor(pal.ColorRole.Base, QColor(0, 0, 0, 0))
        self.setPalette(pal)
        self.viewport().update()


# ---------------------------------------------------------------------------
# Tabs, search, hints, empty states

class PillTabBar(QTabBar):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.colors = current()
        self.setDrawBase(False)
        self.setExpanding(False)
        self.setUsesScrollButtons(False)
        self.setElideMode(Qt.TextElideMode.ElideNone)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._from = QRectF()
        self._to = QRectF()
        self._progress = 1.0
        self._anim: QPropertyAnimation | None = None
        self.currentChanged.connect(self._animate_to)

    def _get_progress(self) -> float:
        return self._progress

    def _set_progress(self, value: float) -> None:
        self._progress = float(value)
        self.update()

    progress = Property(float, _get_progress, _set_progress)

    def _rect_for(self, index: int) -> QRectF:
        if 0 <= index < self.count():
            return QRectF(self.tabRect(index)).adjusted(1, 3, -1, -3)
        return QRectF()

    def _indicator(self) -> QRectF:
        if self._to.isNull():
            return self._rect_for(self.currentIndex())
        t = self._progress
        return QRectF(
            motion.lerp(self._from.x(), self._to.x(), t),
            motion.lerp(self._from.y(), self._to.y(), t),
            motion.lerp(self._from.width(), self._to.width(), t),
            motion.lerp(self._from.height(), self._to.height(), t),
        )

    def _animate_to(self, index: int) -> None:
        target = self._rect_for(index)
        if target.isNull():
            return
        current = self._indicator()
        self._to = target
        if not motion.enabled() or current.isNull():
            self._from = target
            self._progress = 1.0
            self.update()
            return
        self._from = current
        self._progress = 0.0
        _discard_anim(self, "_anim")
        anim = QPropertyAnimation(self, b"progress", self)
        anim.setDuration(220)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._anim = anim

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        rect = self._rect_for(self.currentIndex())
        if not rect.isNull():
            self._from = rect
            self._to = rect
            self._progress = 1.0
            self.update()

    def apply_theme(self, colors: Palette) -> None:
        self.colors = colors
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        c = self.colors
        rect = self._indicator()
        if not rect.isNull() and self.count() > 0:
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            bg = QColor(c.accent)
            bg.setAlpha(44 if c.name == "dark" else 26)
            border = QColor(c.accent)
            border.setAlpha(68 if c.name == "dark" else 48)
            p.setPen(QPen(border, 1))
            p.setBrush(bg)
            p.drawRoundedRect(rect, 8, 8)
            p.end()
        super().paintEvent(event)


class SearchField(QLineEdit):
    def __init__(self, placeholder: str = "搜索", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.colors = current()
        self.setObjectName("searchField")
        self.setPlaceholderText(placeholder)
        self.setClearButtonEnabled(True)
        self.setMinimumHeight(34)
        self._lead = self.addAction(
            icons.make_icon("search", self.colors.text_faint, 16),
            QLineEdit.ActionPosition.LeadingPosition,
        )

    def apply_theme(self, colors: Palette) -> None:
        self.colors = colors
        self._lead.setIcon(icons.make_icon("search", colors.text_faint, 16))


class HintBar(QFrame):
    def __init__(self, text: str = "", tone: str = "info", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("hintBar")
        self.colors = current()
        self.tone_key = tone
        self.icon = QLabel()
        self.icon.setFixedSize(18, 18)
        self.icon.setScaledContents(True)
        self.label = QLabel(text)
        self.label.setObjectName("hintText")
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(11, 9, 11, 9)
        layout.setSpacing(9)
        layout.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.label, 1)
        self.apply_theme(self.colors)

    def setText(self, text: str) -> None:  # noqa: N802
        self.label.setText(text)

    def text(self) -> str:
        return self.label.text()

    def apply_theme(self, colors: Palette) -> None:
        self.colors = colors
        color = tone_color(colors, self.tone_key)
        self.icon.setPixmap(icons.make_pixmap("info", color, 16))
        self.update()


class RoundGlyph(QWidget):
    def __init__(self, glyph: str = "database", size: int = 64, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.glyph = glyph
        self.colors = current()

    def set_glyph(self, glyph: str) -> None:
        self.glyph = glyph
        self.update()

    def apply_theme(self, colors: Palette) -> None:
        self.colors = colors
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        c = self.colors
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        tone = QColor(c.accent)
        bg = QColor(tone)
        bg.setAlpha(28 if c.name == "dark" else 18)
        border = QColor(tone)
        border.setAlpha(54 if c.name == "dark" else 38)
        p.setPen(QPen(border, 1))
        p.setBrush(bg)
        p.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 19, 19)
        icons.paint_glyph(p, self.glyph, QRectF(18, 18, self.width() - 36, self.height() - 36),
                          tone)
        p.end()


class EmptyState(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("emptyState")
        self.colors = current()
        self._handler = None
        self._action_icon = "plus"
        self.glyph = RoundGlyph("database", 64)
        self.title = QLabel("暂无数据")
        self.title.setObjectName("emptyTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text = QLabel("")
        self.text.setObjectName("emptyText")
        self.text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text.setWordWrap(True)
        # A fixed, readable measure keeps wrapped Chinese descriptions from
        # collapsing to a one-line height and clipping above the action button.
        self.text.setFixedWidth(420)
        self.action = QPushButton("")
        self.action.setObjectName("softButton")
        self.action.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action.clicked.connect(self._trigger)
        self.action.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)
        layout.addStretch(1)
        layout.addWidget(self.glyph, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(4)
        layout.addWidget(self.title, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.text, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(4)
        layout.addWidget(self.action, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)

    def _trigger(self) -> None:
        if callable(self._handler):
            self._handler()

    def set_content(
        self,
        glyph: str,
        title: str,
        text: str,
        action_text: str | None = None,
        handler=None,
        action_icon: str = "plus",
    ) -> None:
        self.glyph.set_glyph(glyph)
        self.title.setText(title)
        self.text.setText(text)
        # QLabel can report a one-line height for wrapped text when centered in
        # a QVBoxLayout; pin the computed height so the description never clips.
        self.text.setMinimumHeight(self.text.sizeHint().height())
        self._handler = handler
        self._action_icon = action_icon
        if action_text:
            self.action.setText(action_text)
            self.action.setIcon(icons.make_icon(action_icon, self.colors.accent, 15))
            self.action.show()
        else:
            self.action.hide()

    def apply_theme(self, colors: Palette) -> None:
        self.colors = colors
        self.glyph.apply_theme(colors)
        if self.action.isVisible():
            self.action.setIcon(icons.make_icon(self._action_icon, colors.accent, 15))
        self.update()


# ---------------------------------------------------------------------------
# Toasts

class Toast(QWidget):
    KINDS = {
        "success": ("check", "ok"),
        "error": ("alert", "danger"),
        "warning": ("alert", "warn"),
        "info": ("info", "info"),
    }

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("toast")
        self.colors = current()
        self._text = ""
        self._kind = "info"
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.effect = QGraphicsOpacityEffect(self)
        self.effect.setOpacity(0.0)
        self.setGraphicsEffect(self.effect)
        self.hide()

    def set_content(self, text: str, kind: str = "info") -> None:
        self._text = text
        self._kind = kind if kind in self.KINDS else "info"
        self._resize_to_text()

    def _resize_to_text(self) -> None:
        fm = QFontMetrics(_font(self.font(), 12))
        width = max(250, min(470, fm.horizontalAdvance(self._text) + 76))
        self.resize(width, 56)

    def apply_theme(self, colors: Palette) -> None:
        self.colors = colors
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        c = self.colors
        glyph, tone_key = self.KINDS[self._kind]
        tone = QColor(tone_color(c, tone_key))
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        card = QRectF(7, 6, self.width() - 14, self.height() - 15)

        shadow = QColor(c.shadow)
        shadow.setAlpha(40)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(shadow)
        p.drawRoundedRect(card.adjusted(0, 2, 0, 3), 11, 11)
        p.setBrush(QColor(c.surface))
        p.setPen(QPen(QColor(c.border_strong), 1))
        p.drawRoundedRect(card, 11, 11)

        strip = QColor(tone)
        strip.setAlpha(210)
        p.setBrush(strip)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(card.left() + 1, card.top() + 13, 3, card.height() - 26), 1.5, 1.5)

        circle = QRectF(card.left() + 16, card.center().y() - 13, 26, 26)
        bg = QColor(tone)
        bg.setAlpha(38 if c.name == "dark" else 26)
        p.setBrush(bg)
        p.drawEllipse(circle)
        icons.paint_glyph(p, glyph, circle.adjusted(6, 6, -6, -6), tone)

        _elide(p, self._text,
               QRectF(circle.right() + 10, card.top(), card.width() - 70, card.height()),
               QColor(c.text), _font(self.font(), 12, QFont.Weight.Medium))
        p.end()


class Toaster(QObject):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.parent = parent
        self.toast: Toast | None = None
        self.last_text = ""
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._dismiss)
        self._pos_anim: QPropertyAnimation | None = None
        self._fade_anim: QPropertyAnimation | None = None
        parent.installEventFilter(self)

    def _status_height(self) -> int:
        bar = self.parent.statusBar() if hasattr(self.parent, "statusBar") else None
        return bar.height() if bar is not None else 0

    def _target(self) -> QPoint:
        toast = self.toast
        if toast is None:
            return QPoint(0, 0)
        x = max(12, self.parent.width() - toast.width() - 16)
        y = max(12, self.parent.height() - self._status_height() - toast.height() - 12)
        return QPoint(x, y)

    def show(self, text: str, kind: str = "info", timeout: int = 2800) -> None:
        if self.toast is None:
            self.toast = Toast(self.parent)
        toast = self.toast
        toast.set_content(text, kind)
        self.last_text = text
        target = self._target()
        was_visible = toast.isVisible()
        if not was_visible:
            toast.move(target.x(), target.y() + 18)
            toast.effect.setOpacity(0.0)
            toast.show()
            toast.raise_()
        else:
            toast.effect.setOpacity(1.0)
        toast.apply_theme(current())
        toast.raise_()

        _discard_anim(self, "_pos_anim")
        _discard_anim(self, "_fade_anim")
        if motion.enabled():
            if not was_visible:
                pos = QPropertyAnimation(toast, b"pos", toast)
                pos.setDuration(240)
                pos.setStartValue(QPoint(target.x(), target.y() + 18))
                pos.setEndValue(target)
                pos.setEasingCurve(QEasingCurve.Type.OutCubic)
                pos.start()
                self._pos_anim = pos
            fade = QPropertyAnimation(toast.effect, b"opacity", toast)
            fade.setDuration(180)
            fade.setStartValue(toast.effect.opacity())
            fade.setEndValue(1.0)
            fade.start()
            self._fade_anim = fade
        else:
            toast.move(target)
            toast.effect.setOpacity(1.0)
        self.timer.start(timeout)

    def _dismiss(self) -> None:
        toast = self.toast
        if toast is None or not toast.isVisible():
            return
        if not motion.enabled():
            toast.hide()
            return
        _discard_anim(self, "_fade_anim")
        fade = QPropertyAnimation(toast.effect, b"opacity", toast)
        fade.setDuration(180)
        fade.setStartValue(toast.effect.opacity())
        fade.setEndValue(0.0)
        fade.finished.connect(toast.hide)
        fade.start()
        self._fade_anim = fade

    def apply_theme(self, colors: Palette) -> None:
        if self.toast is not None:
            self.toast.apply_theme(colors)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is self.parent and event.type() == QEvent.Type.Resize:
            if self.toast is not None and self.toast.isVisible():
                self.toast.move(self._target())
        return False


def divider(vertical: bool = False, object_name: str = "divider") -> QFrame:
    line = QFrame()
    line.setObjectName(object_name)
    if vertical:
        line.setFixedWidth(1)
        line.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
    else:
        line.setFixedHeight(1)
        line.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return line
