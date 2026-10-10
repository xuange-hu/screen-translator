"""监控区域选择器：监控进行中可拖拽/缩放调整抓取范围（实时更新）。"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from utils import dpi_utils


class MonitorRegionSelector(QWidget):
    # physical (mss) bbox, 实时跟随拖拽
    region_changed = Signal(object)
    # physical (mss) bbox, 拖拽/缩放结束时触发一次
    region_committed = Signal(object)
    # 双击停止监控
    stop_requested = Signal()

    _HANDLE = 9

    def __init__(self, monitor_map, physical_bbox, accent: str = "#2878E8", parent=None) -> None:
        super().__init__(parent)
        self._monitor_map = monitor_map
        self._accent = QColor(accent)
        self._highlight_color = QColor(accent)
        self._dragging = False
        self._resize_dir = 0
        self._drag_offset = QPoint()
        self._base_geometry = self._physical_to_geometry(physical_bbox)
        self._geometry = QRect(self._base_geometry)
        self._physical = tuple(physical_bbox)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setGeometry(self._geometry)

        self._pulse_t = 0.0
        self._pulse = QVariantAnimation(self)
        self._pulse.setStartValue(0.0)
        self._pulse.setEndValue(1.0)
        self._pulse.setDuration(1100)
        self._pulse.setLoopCount(-1)
        self._pulse.valueChanged.connect(self._set_pulse)
        self._pulse.start()

    # --------------------------------------------------------- coordinate mapping
    def _physical_to_geometry(self, physical) -> QRect:
        cx = (physical[0] + physical[2]) // 2
        cy = (physical[1] + physical[3]) // 2
        monitor = dpi_utils.monitor_for_physical_point(cx, cy, self._monitor_map)
        geo = dpi_utils.physical_rect_to_overlay_geometry(physical, monitor)
        return QRect(geo[0], geo[1], geo[2], geo[3])

    def _geometry_to_physical(self, geo: QRect):
        logical = (geo.x(), geo.y(), geo.x() + geo.width(), geo.y() + geo.height())
        parts = dpi_utils.logical_rect_to_physical_parts(logical, self._monitor_map)
        if not parts:
            return None
        return dpi_utils.union_rects(parts)

    def set_physical_bbox(self, physical) -> None:
        self._physical = tuple(physical)
        self._geometry = self._physical_to_geometry(physical)
        self.setGeometry(self._geometry)

    # --------------------------------------------------------- hit testing
    def _hit_test(self, pos: QPoint) -> int:
        h = self._HANDLE
        x, y = pos.x(), pos.y()
        w, ht = self.width(), self.height()
        left = x <= h
        right = x >= w - h
        top = y <= h
        bottom = y >= ht - h
        if left and top:
            return 1
        if right and top:
            return 2
        if left and bottom:
            return 3
        if right and bottom:
            return 4
        if left:
            return 5
        if right:
            return 6
        if top:
            return 7
        if bottom:
            return 8
        return 0

    def _apply_cursor(self, pos: QPoint) -> None:
        d = self._hit_test(pos)
        cursors = {
            0: Qt.CursorShape.SizeAllCursor,
            1: Qt.CursorShape.SizeFDiagCursor,
            2: Qt.CursorShape.SizeBDiagCursor,
            3: Qt.CursorShape.SizeFDiagCursor,
            4: Qt.CursorShape.SizeBDiagCursor,
            5: Qt.CursorShape.SizeHorCursor,
            6: Qt.CursorShape.SizeHorCursor,
            7: Qt.CursorShape.SizeVerCursor,
            8: Qt.CursorShape.SizeVerCursor,
        }
        self.setCursor(cursors[d])

    # --------------------------------------------------------- mouse
    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._dragging = True
        self._resize_dir = self._hit_test(event.position().toPoint())
        self._drag_offset = event.position().toPoint()
        self._base_geometry = QRect(self._geometry)
        self._pulse.stop()

    def mouseMoveEvent(self, event) -> None:
        pos = event.position().toPoint()
        if not self._dragging:
            self._apply_cursor(pos)
            return
        delta = pos - self._drag_offset
        g = QRect(self._base_geometry)
        d = self._resize_dir
        min_w, min_h = 32, 32
        if d == 0:
            g.translate(delta)
        else:
            if d in (1, 3, 5):
                g.setLeft(min(g.left() + delta.x(), g.right() - min_w))
            if d in (2, 4, 6):
                g.setRight(max(g.right() + delta.x(), g.left() + min_w))
            if d in (1, 2, 7):
                g.setTop(min(g.top() + delta.y(), g.bottom() - min_h))
            if d in (3, 4, 8):
                g.setBottom(max(g.bottom() + delta.y(), g.top() + min_h))
        self._geometry = g
        self.setGeometry(g)
        physical = self._geometry_to_physical(g)
        if physical is not None:
            self._physical = physical
            self.region_changed.emit(physical)

    def mouseReleaseEvent(self, event) -> None:
        if not self._dragging:
            return
        self._dragging = False
        self._resize_dir = 0
        physical = self._geometry_to_physical(self._geometry)
        if physical is not None:
            self._physical = physical
            self.region_committed.emit(physical)
        self._apply_cursor(event.position().toPoint())

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.stop_requested.emit()

    # --------------------------------------------------------- paint
    def _set_pulse(self, value) -> None:
        self._pulse_t = float(value)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        fill = QColor(self._accent)
        fill.setAlpha(14)
        painter.fillRect(self.rect(), fill)

        pulse = 0.5 + 0.5 * (1.0 - abs(1.0 - 2.0 * self._pulse_t))
        border = QColor(self._accent)
        border.setAlpha(int(200 + 45 * pulse))
        painter.setPen(QPen(border, 1.6 + 0.6 * pulse))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.rect().adjusted(1, 1, -2, -2))

        handle = QColor(self._accent)
        handle.setAlpha(235)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(handle)
        hh = self._HANDLE
        for cx, cy in (
            (hh // 2, hh // 2),
            (w - hh // 2, hh // 2),
            (hh // 2, h - hh // 2),
            (w - hh // 2, h - hh // 2),
        ):
            painter.drawRoundedRect(cx - 3, cy - 3, 6, 6, 2, 2)

        text = "拖拽调整 · 双击停止"
        font = QFont()
        font.setFamilies(["Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI"])
        font.setPixelSize(12)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        badge_w = metrics.horizontalAdvance(text) + 22
        badge_h = 26
        bx = max(2, min(w - badge_w - 2, 2))
        by = max(2, h - badge_h - 6) if h > badge_h + 12 else 2
        painter.setPen(QPen(QColor("#DEDCD5"), 1))
        painter.setBrush(QColor("#FFFEFC"))
        painter.drawRoundedRect(bx, by, badge_w, badge_h, 8, 8)
        painter.setPen(self._accent)
        painter.drawText(
            bx + 11, by, badge_w - 16, badge_h,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            text,
        )
