"""Small, dependency-free motion helpers.

The rule for this app is that every animation is short (120–400 ms), never
blocks input, and can be switched off globally from the 外观 menu.  Background
refreshes (250 ms) keep running untouched while animations play.
"""

from __future__ import annotations

from PySide6.QtCore import (
    QAbstractAnimation, QEasingCurve, QEvent, QObject, QPointF,
    QPropertyAnimation,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QWidget

_ENABLED = True


def enabled() -> bool:
    return _ENABLED


def set_enabled(value: bool) -> None:
    global _ENABLED
    _ENABLED = bool(value)


def duration(ms: int) -> int:
    return ms if _ENABLED else 0


def animate(
    target: QObject,
    prop: bytes,
    start,
    end,
    ms: int = 180,
    easing: QEasingCurve.Type = QEasingCurve.Type.OutCubic,
    on_finished=None,
) -> QPropertyAnimation | None:
    """Animate a Qt property, or jump straight to the end when motion is off."""

    if not _ENABLED or ms <= 0:
        target.setProperty(prop, end)
        if on_finished is not None:
            on_finished()
        return None
    anim = QPropertyAnimation(target, prop, target)
    anim.setDuration(ms)
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.setEasingCurve(easing)
    if on_finished is not None:
        anim.finished.connect(on_finished)
    anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * max(0.0, min(1.0, t))


def lerp_color(a: str | QColor, b: str | QColor, t: float) -> QColor:
    c1, c2 = QColor(a), QColor(b)
    t = max(0.0, min(1.0, t))
    return QColor(
        round(c1.red() + (c2.red() - c1.red()) * t),
        round(c1.green() + (c2.green() - c1.green()) * t),
        round(c1.blue() + (c2.blue() - c1.blue()) * t),
        round(c1.alpha() + (c2.alpha() - c1.alpha()) * t),
    )


def fade_in(widget: QWidget, ms: int = 200, low: float = 0.0, high: float = 1.0) -> None:
    """Fade a widget in once, cleaning the effect up afterwards."""

    if not _ENABLED:
        return
    if widget.graphicsEffect() is not None:
        return
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(low)
    widget.setGraphicsEffect(effect)

    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(ms)
    anim.setStartValue(low)
    anim.setEndValue(high)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def clean() -> None:
        widget.setGraphicsEffect(None)

    anim.finished.connect(clean)
    anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)


def fade_window(widget: QWidget, ms: int = 180) -> None:
    """Fade a top-level window in without touching its layout."""

    if not _ENABLED:
        return
    widget.setWindowOpacity(0.02)
    anim = QPropertyAnimation(widget, b"windowOpacity", widget)
    anim.setDuration(ms)
    anim.setStartValue(0.02)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)


def card_shadow(widget: QWidget, color: str, alpha: int = 38, blur: float = 20, dy: float = 4) -> QGraphicsDropShadowEffect:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, dy)
    c = QColor(color)
    c.setAlpha(alpha)
    effect.setColor(c)
    widget.setGraphicsEffect(effect)
    return effect


class HoverShadow(QObject):
    """Animate a subtle lift shadow while the pointer is over a card/button."""

    def __init__(
        self,
        widget: QWidget,
        color: str,
        alpha: int = 40,
        rest_blur: float = 16,
        hover_blur: float = 32,
        rest_dy: float = 3,
        hover_dy: float = 7,
    ) -> None:
        super().__init__(widget)
        self.widget = widget
        self._rest_blur = rest_blur
        self._hover_blur = hover_blur
        self._rest_dy = rest_dy
        self._hover_dy = hover_dy
        self._anim: QPropertyAnimation | None = None
        self._offset_anim: QPropertyAnimation | None = None
        self.effect = card_shadow(widget, color, alpha, rest_blur, rest_dy)
        widget.installEventFilter(self)

    def set_color(self, color: str, alpha: int = 40) -> None:
        c = QColor(color)
        c.setAlpha(alpha)
        self.effect.setColor(c)

    def _run(self, hover: bool) -> None:
        if not _ENABLED:
            self.effect.setBlurRadius(self._hover_blur if hover else self._rest_blur)
            self.effect.setOffset(0, self._hover_dy if hover else self._rest_dy)
            return

        blur_from = self.effect.blurRadius()
        blur_to = self._hover_blur if hover else self._rest_blur
        blur = QPropertyAnimation(self.effect, b"blurRadius", self.widget)
        blur.setDuration(200)
        blur.setStartValue(blur_from)
        blur.setEndValue(blur_to)
        blur.setEasingCurve(QEasingCurve.Type.OutCubic)
        blur.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
        self._anim = blur

        off_from = self.effect.offset()
        off_to = QPointF(0, self._hover_dy if hover else self._rest_dy)
        offset = QPropertyAnimation(self.effect, b"offset", self.widget)
        offset.setDuration(200)
        offset.setStartValue(off_from)
        offset.setEndValue(off_to)
        offset.setEasingCurve(QEasingCurve.Type.OutCubic)
        offset.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
        self._offset_anim = offset

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is self.widget:
            if event.type() == QEvent.Type.Enter:
                self._run(True)
            elif event.type() == QEvent.Type.Leave:
                self._run(False)
        return False


def shadow_color(colors, alpha: int = 38) -> QColor:
    c = QColor(colors.shadow)
    c.setAlpha(alpha)
    return c
