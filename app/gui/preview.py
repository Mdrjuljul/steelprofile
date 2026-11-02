"""Aperçu 2D **exact** de la section, peint avec `QPainter`.

Le chemin est construit avec les mêmes tronçons que les exports (≤ 90°), donc
avec de vrais arcs de cercle : rien n'est facetté pour l'affichage. Le repère
logique est celui du moteur (y vers la droite, z vers le haut) ; la vue applique
une transformation d'écran, ce qui laisse la géométrie intacte.

Interactions : molette = zoom sous le curseur, glisser = déplacement,
double-clic = ajuster à la fenêtre.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
)
from PySide6.QtWidgets import QWidget

from app.exports.curve import contour_segments
from app.geometry.contour import Section
from app.geometry.properties import SectionProperties

FILL_LIGHT = QColor(96, 125, 160)
STROKE_LIGHT = QColor(32, 52, 78)
FILL_DARK = QColor(126, 160, 200)
STROKE_DARK = QColor(196, 214, 236)


def section_path(section: Section) -> QPainterPath:
    """Chemin Qt exact d'une section : droites et arcs réels, trous compris.

    Le remplissage en règle pair-impair traite les trous sans orientation
    particulière : les contours extérieurs et intérieurs sont tous ajoutés au
    même chemin, exactement comme le fait le DXF.
    """
    path = QPainterPath()
    path.setFillRule(Qt.FillRule.OddEvenFill)
    for contour in section.contours:
        segments = contour_segments(contour)
        if not segments:
            continue
        path.moveTo(*segments[0].start)
        for segment in segments:
            if segment.is_arc:
                radius = segment.radius
                cy, cz = segment.center  # type: ignore[misc]
                rect = QRectF(cy - radius, cz - radius, 2.0 * radius, 2.0 * radius)
                # Qt mesure les angles depuis 3 h dans le sens trigonométrique
                # visuel, avec y vers le bas : thêta_section = −thêta_Qt.
                path.arcTo(rect, -math.degrees(segment.theta0),
                           -math.degrees(segment.sweep))
            else:
                path.lineTo(*segment.end)
        path.closeSubpath()
    return path


def nice_step(target: float) -> float:
    """Pas « rond » (1, 2 ou 5 × 10ⁿ) le plus proche au-dessus de `target`."""
    if not target > 0.0:
        return 1.0
    exponent = math.floor(math.log10(target))
    base = 10.0 ** exponent
    for factor in (1.0, 2.0, 5.0, 10.0):
        if base * factor >= target:
            return base * factor
    return base * 10.0


class SectionPreview(QWidget):
    """Vue 2D de la section, avec zoom, déplacement et axes principaux."""

    ZOOM_MIN = 1.0e-4
    ZOOM_MAX = 1.0e4

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(260, 260)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._section: Section | None = None
        self._properties: SectionProperties | None = None
        self._path = QPainterPath()
        self._scale = 1.0
        self._origin = QPointF(0.0, 0.0)
        self._autofit = True
        self._show_grid = True
        self._show_axes = True
        self._placeholder = "Sélectionnez un profilé dans le catalogue"
        self._panning = False
        self._last_pos = QPointF()

    # -- contenu -----------------------------------------------------------
    def set_section(self, section: Section | None,
                    properties: SectionProperties | None = None) -> None:
        self._section = section
        self._properties = properties
        self._path = section_path(section) if section is not None else QPainterPath()
        self._autofit = True
        self.fit()
        self.update()

    def set_placeholder(self, text: str) -> None:
        """Message affiché quand aucune section n'est dessinée."""
        self._placeholder = text
        self.update()

    def clear(self, placeholder: str | None = None) -> None:
        if placeholder is not None:
            self._placeholder = placeholder
        self.set_section(None, None)

    def has_section(self) -> bool:
        return self._section is not None

    # -- affichage ---------------------------------------------------------
    def set_show_grid(self, enabled: bool) -> None:
        self._show_grid = bool(enabled)
        self.update()

    def set_show_axes(self, enabled: bool) -> None:
        self._show_axes = bool(enabled)
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(520, 520)

    def to_device(self, y: float, z: float) -> QPointF:
        return QPointF(self._origin.x() + self._scale * y,
                       self._origin.y() - self._scale * z)

    def to_world(self, point: QPointF) -> tuple[float, float]:
        return ((point.x() - self._origin.x()) / self._scale,
                (self._origin.y() - point.y()) / self._scale)

    def fit(self) -> None:
        """Ajuste la vue à l'encombrement de la section, avec une marge."""
        if self._section is None:
            self._autofit = True
            self._scale = 1.0
            self._origin = QPointF(self.width() / 2.0, self.height() / 2.0)
            self.update()
            return
        y_min, y_max, z_min, z_max = self._section.bounds()
        width = max(y_max - y_min, 1e-9)
        height = max(z_max - z_min, 1e-9)
        margin = 0.86
        available_w = max(self.width() - 24.0, 32.0)
        available_h = max(self.height() - 24.0, 32.0)
        self._scale = max(min(available_w / width, available_h / height) * margin,
                          self.ZOOM_MIN)
        self._scale = min(self._scale, self.ZOOM_MAX)
        cy = (y_min + y_max) / 2.0
        cz = (z_min + z_max) / 2.0
        self._origin = QPointF(self.width() / 2.0 - self._scale * cy,
                               self.height() / 2.0 + self._scale * cz)
        self._autofit = True
        self.update()

    def zoom(self, factor: float, anchor: QPointF | None = None) -> None:
        if self._section is None or not factor > 0.0:
            return
        anchor = anchor if anchor is not None else QPointF(
            self.width() / 2.0, self.height() / 2.0)
        new_scale = min(max(self._scale * factor, self.ZOOM_MIN), self.ZOOM_MAX)
        factor = new_scale / self._scale
        if factor == 1.0:
            return
        self._origin = QPointF(
            anchor.x() + (self._origin.x() - anchor.x()) * factor,
            anchor.y() + (self._origin.y() - anchor.y()) * factor,
        )
        self._scale = new_scale
        self._autofit = False
        self.update()

    def zoom_in(self) -> None:
        self.zoom(1.25)

    def zoom_out(self) -> None:
        self.zoom(1.0 / 1.25)

    # -- événements --------------------------------------------------------
    def resizeEvent(self, event) -> None:  # noqa: N802 - API Qt
        if self._autofit or self._section is None:
            self.fit()
        super().resizeEvent(event)

    def wheelEvent(self, event) -> None:  # noqa: N802 - API Qt
        if self._section is None:
            return
        steps = event.angleDelta().y() / 120.0
        if steps:
            self.zoom(1.18 ** steps, event.position())
        event.accept()

    def mousePressEvent(self, event) -> None:  # noqa: N802 - API Qt
        if event.button() == Qt.MouseButton.LeftButton and self._section is not None:
            self._panning = True
            self._last_pos = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - API Qt
        if self._panning:
            delta = event.position() - self._last_pos
            self._last_pos = event.position()
            self._origin = QPointF(self._origin.x() + delta.x(),
                                   self._origin.y() + delta.y())
            self._autofit = False
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - API Qt
        if event.button() == Qt.MouseButton.LeftButton:
            self._panning = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 - API Qt
        self.fit()

    # -- peinture ----------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802 - API Qt
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        palette = self.palette()
        dark = palette.color(QPalette.ColorRole.Window).lightness() < 128
        background = palette.color(QPalette.ColorRole.Base)
        painter.fillRect(self.rect(), background)

        if self._section is None:
            painter.setPen(QPen(palette.color(QPalette.ColorRole.Mid), 1))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             self._placeholder)
            return

        if self._show_grid:
            self._draw_grid(painter, dark)

        fill = QColor(FILL_DARK if dark else FILL_LIGHT)
        fill.setAlpha(70 if dark else 60)
        stroke = QColor(STROKE_DARK if dark else STROKE_LIGHT)
        pen = QPen(stroke, 1.6)
        pen.setCosmetic(True)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

        painter.save()
        painter.translate(self._origin)
        painter.scale(self._scale, -self._scale)
        painter.setBrush(fill)
        painter.setPen(pen)
        painter.drawPath(self._path)
        painter.restore()

        self._draw_overlays(painter, stroke, dark)

    def _draw_grid(self, painter: QPainter, dark: bool) -> None:
        step = nice_step(64.0 / self._scale)
        colour = QColor(255, 255, 255, 26) if dark else QColor(0, 0, 0, 20)
        pen = QPen(colour, 1)
        pen.setCosmetic(True)
        painter.setPen(pen)
        y_min, y_max = self.to_world(QPointF(0, 0))[0], self.to_world(
            QPointF(self.width(), 0))[0]
        z_top, z_bottom = self.to_world(QPointF(0, 0))[1], self.to_world(
            QPointF(0, self.height()))[1]
        start = math.floor(y_min / step) * step
        value = start
        while value <= y_max and (value - start) / step < 400:
            x = self.to_device(value, 0.0).x()
            painter.drawLine(QPointF(x, 0.0), QPointF(x, float(self.height())))
            value += step
        start = math.floor(z_bottom / step) * step
        value = start
        while value <= z_top and (value - start) / step < 400:
            y = self.to_device(0.0, value).y()
            painter.drawLine(QPointF(0.0, y), QPointF(float(self.width()), y))
            value += step

    def _draw_overlays(self, painter: QPainter, stroke: QColor, dark: bool) -> None:
        assert self._section is not None
        muted = QColor(stroke)
        muted.setAlpha(120)
        dashed = QPen(muted, 1, Qt.PenStyle.DashLine)
        dashed.setCosmetic(True)
        painter.setPen(dashed)
        y_min, y_max, z_min, z_max = self._section.bounds()
        top_left = self.to_device(y_min, z_max)
        bottom_right = self.to_device(y_max, z_min)
        painter.drawRect(QRectF(top_left, bottom_right))

        if self._show_axes and self._properties is not None:
            props = self._properties
            centre = self.to_device(props.y_c, props.z_c)
            reach = 0.42 * min(self.width(), self.height())
            angle = math.radians(props.alpha_deg)
            for sign, style in ((1.0, Qt.PenStyle.DashDotLine),
                                (-1.0, Qt.PenStyle.DashLine)):
                dx = sign * math.cos(angle) * reach
                dy = -sign * math.sin(angle) * reach
                pen = QPen(QColor(196, 118, 74) if not dark else QColor(232, 160, 110),
                           1.2, style)
                pen.setCosmetic(True)
                painter.setPen(pen)
                painter.drawLine(centre + QPointF(dx, dy), centre - QPointF(dx, dy))

        if self._properties is not None:
            centre = self.to_device(self._properties.y_c, self._properties.z_c)
            marker = QPen(QColor(200, 90, 70), 1.2)
            marker.setCosmetic(True)
            painter.setPen(marker)
            painter.drawEllipse(centre, 4.0, 4.0)
            painter.drawLine(centre + QPointF(-7, 0), centre + QPointF(7, 0))
            painter.drawLine(centre + QPointF(0, -7), centre + QPointF(0, 7))
            font = QFont(painter.font())
            font.setPointSizeF(max(font.pointSizeF() * 0.9, 7.0))
            painter.setFont(font)
            painter.drawText(centre + QPointF(9, -6), "G")

        font = QFont(painter.font())
        font.setPointSizeF(max(font.pointSizeF() * 0.88, 7.0))
        painter.setFont(font)
        painter.setPen(QPen(QColor(stroke), 1))
        metrics = QFontMetrics(font)
        y0, y1, z0, z1 = self._section.bounds()
        text = (f"encombrement {y1 - y0:g} × {z1 - z0:g} mm"
                f"   ·   zoom {self._scale:.3g} px/mm")
        painter.drawText(8, self.height() - 8 - metrics.descent(), text)
