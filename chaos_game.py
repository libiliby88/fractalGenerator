"""Chaos Game visualizer with PyQt6."""

from __future__ import annotations

import math
import random
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np
from PyQt6.QtCore import QPointF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QKeyEvent, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

Point = Tuple[float, float]


@dataclass
class Vertex:
    x: float
    y: float
    index: int

    def position(self) -> Point:
        return self.x, self.y

    def set_position(self, x: float, y: float) -> None:
        self.x = x
        self.y = y


@dataclass
class ChaosPoint:
    """A generated point with stored distances to each vertex."""

    x: float
    y: float
    distances: np.ndarray = field(repr=False)

    def position(self) -> Point:
        return self.x, self.y

    def set_position(self, x: float, y: float) -> None:
        self.x = x
        self.y = y


def default_vertices(count: int, width: float, height: float, margin: float = 60.0) -> List[Vertex]:
    """Place vertices evenly on an ellipse inside the canvas."""
    cx = width / 2.0
    cy = height / 2.0
    rx = (width - 2 * margin) / 2.0
    ry = (height - 2 * margin) / 2.0
    vertices: List[Vertex] = []
    for i in range(count):
        angle = 2.0 * math.pi * i / count - math.pi / 2.0
        vertices.append(
            Vertex(
                cx + rx * math.cos(angle),
                cy + ry * math.sin(angle),
                index=i + 1,
            )
        )
    return vertices


def distance(p: Point, q: Point) -> float:
    return math.hypot(p[0] - q[0], p[1] - q[1])


def compute_distances(point: Point, vertices: List[Vertex]) -> np.ndarray:
    return np.array([distance(point, v.position()) for v in vertices], dtype=float)


def vertex_positions(vertices: List[Vertex]) -> List[Point]:
    return [v.position() for v in vertices]


def find_vertex_by_index(vertices: List[Vertex], index: int) -> Optional[Vertex]:
    for vertex in vertices:
        if vertex.index == index:
            return vertex
    return None


def consecutive_vertex_links(vertices: List[Vertex]) -> List[Tuple[Vertex, Vertex]]:
    """Return edges only between vertices whose indices differ by exactly 1."""
    ordered = sorted(vertices, key=lambda v: v.index)
    links: List[Tuple[Vertex, Vertex]] = []
    for left, right in zip(ordered, ordered[1:]):
        if right.index - left.index == 1:
            links.append((left, right))
    return links


def connected_components(vertices: List[Vertex]) -> List[List[Vertex]]:
    """Group vertices into connected chains of consecutive indices."""
    ordered = sorted(vertices, key=lambda v: v.index)
    if not ordered:
        return []

    components: List[List[Vertex]] = [[ordered[0]]]
    for vertex in ordered[1:]:
        if vertex.index - components[-1][-1].index == 1:
            components[-1].append(vertex)
        else:
            components.append([vertex])
    return components


def component_centroid(component: List[Vertex]) -> Point:
    count = len(component)
    return (
        sum(vertex.x for vertex in component) / count,
        sum(vertex.y for vertex in component) / count,
    )


def nearest_component_index(point: Point, components: List[List[Vertex]]) -> int:
    best_index = 0
    best_distance = float("inf")
    for index, component in enumerate(components):
        centroid = component_centroid(component)
        dist = distance(point, centroid)
        if dist < best_distance:
            best_distance = dist
            best_index = index
    return best_index


def shift_to_next_connected_graph(
    current: Point,
    vertices: List[Vertex],
    fraction: float,
) -> Point:
    """
    Move the current point to the next connected graph while preserving
    distance ratios to every end vertex.
    """
    reference_distances = compute_distances(current, vertices)
    components = connected_components(vertices)

    if len(components) <= 1:
        return reposition_by_distance_ratios(reference_distances, vertices, current)

    current_component = nearest_component_index(current, components)
    next_component = (current_component + 1) % len(components)

    current_centroid = component_centroid(components[current_component])
    next_centroid = component_centroid(components[next_component])

    tentative = (
        current[0] + fraction * (next_centroid[0] - current_centroid[0]),
        current[1] + fraction * (next_centroid[1] - current_centroid[1]),
    )
    return reposition_by_distance_ratios(reference_distances, vertices, tentative)


def reposition_by_distance_ratios(
    reference_distances: np.ndarray,
    vertices: List[Vertex],
    start: Point,
    iterations: int = 16,
) -> Point:
    """
    Reposition a point so ratios of distance to each vertex stay unchanged.

    reference_distances[i] is the distance to vertex i when the point was created.
    """
    if len(vertices) == 0:
        return start

    ref = np.asarray(reference_distances, dtype=float)
    if np.any(ref < 1e-9):
        return start

    target_ratios = ref / ref[0]
    x, y = float(start[0]), float(start[1])

    for _ in range(iterations):
        dists = np.array(
            [math.hypot(x - vx, y - vy) for vx, vy in vertex_positions(vertices)],
            dtype=float,
        )
        if dists[0] < 1e-9:
            break

        current_ratios = dists / dists[0]
        grad_x = 0.0
        grad_y = 0.0

        for (vx, vy), dist, target_ratio in zip(vertex_positions(vertices), dists, target_ratios):
            if dist < 1e-9:
                continue
            error = dist / dists[0] - target_ratio
            dx = x - vx
            dy = y - vy
            grad_x += error * (dx / dist - dx / dists[0])
            grad_y += error * (dy / dist - dy / dists[0])

        x -= 0.25 * grad_x
        y -= 0.25 * grad_y

    return x, y


def lerp_point(current: Point, target: Point, fraction: float) -> Point:
    return (
        current[0] + fraction * (target[0] - current[0]),
        current[1] + fraction * (target[1] - current[1]),
    )


class ChaosCanvas(QWidget):
    """Interactive canvas for the chaos game."""

    step_requested = pyqtSignal()
    vertex_indices_changed = pyqtSignal()

    HIT_RADIUS = 14.0

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(640, 480)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._vertices: List[Vertex] = []
        self._initial_point: Point = (320.0, 240.0)
        self._current_point: Point = self._initial_point
        self._chaos_points: List[ChaosPoint] = []
        self._fraction: float = 0.75

        self._drag_target: Optional[str] = None
        self._drag_index: int = -1
        self._drag_offset: Point = (0.0, 0.0)
        self._vertex_positions_before_drag: List[Vertex] = []

        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor(18, 18, 24))
        self.setPalette(palette)

    def vertices(self) -> List[Vertex]:
        return self._vertices

    def set_vertex_count(self, count: int) -> None:
        self._vertices = default_vertices(count, self.width(), self.height())
        self.reset_trajectory()
        self.vertex_indices_changed.emit()
        self.update()

    def set_vertex_index(self, list_index: int, new_index: int) -> bool:
        if not (0 <= list_index < len(self._vertices)):
            return False

        for i, vertex in enumerate(self._vertices):
            if i != list_index and vertex.index == new_index:
                return False

        self._vertices[list_index].index = new_index
        self.vertex_indices_changed.emit()
        self.update()
        return True

    def set_fraction(self, fraction: float) -> None:
        self._fraction = fraction

    def reset_trajectory(self) -> None:
        self._current_point = self._initial_point
        self._chaos_points.clear()

    def clear_points(self) -> None:
        self._chaos_points.clear()
        self._current_point = self._initial_point
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not self._vertices:
            self.set_vertex_count(3)
        else:
            self._initial_point = (self.width() / 2.0, self.height() / 2.0)
            self._current_point = self._initial_point

    def generate_next_point(self) -> bool:
        if not self._vertices:
            return False

        max_index = max(vertex.index for vertex in self._vertices)
        chosen = round(random.uniform(1, max_index))
        chosen = max(1, min(max_index, chosen))

        target_vertex = find_vertex_by_index(self._vertices, chosen)
        if target_vertex is None:
            new_point = shift_to_next_connected_graph(
                self._current_point,
                self._vertices,
                self._fraction,
            )
        else:
            target = target_vertex.position()
            new_point = lerp_point(self._current_point, target, self._fraction)
        dists = compute_distances(new_point, self._vertices)
        self._chaos_points.append(ChaosPoint(new_point[0], new_point[1], dists))
        self._current_point = new_point
        self.update()
        return True

    def _hit_test(self, pos: Point) -> Tuple[Optional[str], int]:
        px, py = pos
        if distance((px, py), self._initial_point) <= self.HIT_RADIUS:
            return "initial", -1

        for index, vertex in enumerate(self._vertices):
            if distance((px, py), vertex.position()) <= self.HIT_RADIUS:
                return "vertex", index

        return None, -1

    def _sync_chaos_points_to_vertices(self) -> None:
        for chaos_point in self._chaos_points:
            new_pos = reposition_by_distance_ratios(
                chaos_point.distances,
                self._vertices,
                chaos_point.position(),
            )
            chaos_point.set_position(new_pos[0], new_pos[1])

        ref_dists = compute_distances(self._current_point, self._vertex_positions_before_drag)
        self._current_point = reposition_by_distance_ratios(
            ref_dists,
            self._vertices,
            self._current_point,
        )

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return

        pos = (event.position().x(), event.position().y())
        target, index = self._hit_test(pos)

        if target is None:
            return

        self._drag_target = target
        self._drag_index = index
        self._vertex_positions_before_drag = [
            Vertex(v.x, v.y, v.index) for v in self._vertices
        ]

        if target == "initial":
            anchor = self._initial_point
        else:
            anchor = self._vertices[index].position()

        self._drag_offset = (pos[0] - anchor[0], pos[1] - anchor[1])
        self.setFocus()

    def mouseMoveEvent(self, event) -> None:
        pos = (event.position().x(), event.position().y())

        if self._drag_target == "initial":
            self._initial_point = (pos[0] - self._drag_offset[0], pos[1] - self._drag_offset[1])
            self._current_point = self._initial_point
            self.update()
            return

        if self._drag_target == "vertex" and 0 <= self._drag_index < len(self._vertices):
            self._vertices[self._drag_index].set_position(
                pos[0] - self._drag_offset[0],
                pos[1] - self._drag_offset[1],
            )
            self._sync_chaos_points_to_vertices()
            self.update()
            return

        target, _ = self._hit_test(pos)
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if target is not None
            else Qt.CursorShape.ArrowCursor
        )

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_target = None
            self._drag_index = -1
            self._vertex_positions_before_drag.clear()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if not event.isAutoRepeat():
            self.step_requested.emit()
        event.accept()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        self._draw_chaos_points(painter)
        self._draw_links(painter)
        self._draw_vertices(painter)
        self._draw_initial_point(painter)
        self._draw_current_point(painter)

    def _draw_chaos_points(self, painter: QPainter) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(120, 210, 255, 180)))
        for chaos_point in self._chaos_points:
            painter.drawEllipse(QPointF(chaos_point.x, chaos_point.y), 1.6, 1.6)

    def _draw_links(self, painter: QPainter) -> None:
        painter.setPen(QPen(QColor(70, 70, 90), 1, Qt.PenStyle.DashLine))
        for left, right in consecutive_vertex_links(self._vertices):
            a = left.position()
            b = right.position()
            painter.drawLine(QPointF(a[0], a[1]), QPointF(b[0], b[1]))

    def _draw_vertices(self, painter: QPainter) -> None:
        font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        painter.setFont(font)

        for vertex in self._vertices:
            vx, vy = vertex.position()
            painter.setPen(QPen(QColor(255, 180, 80), 2))
            painter.setBrush(QBrush(QColor(255, 140, 40)))
            painter.drawEllipse(QPointF(vx, vy), 10, 10)

            painter.setPen(QPen(QColor(255, 240, 220)))
            label = str(vertex.index)
            painter.drawText(QPointF(vx - 4 * len(label) * 0.25, vy + 4), label)

    def _draw_initial_point(self, painter: QPainter) -> None:
        ix, iy = self._initial_point
        painter.setPen(QPen(QColor(120, 255, 160), 2))
        painter.setBrush(QBrush(QColor(70, 210, 120)))
        painter.drawEllipse(QPointF(ix, iy), 9, 9)

        painter.setPen(QPen(QColor(180, 255, 200)))
        painter.drawText(QPointF(ix + 12, iy - 8), "Start")

    def _draw_current_point(self, painter: QPainter) -> None:
        cx, cy = self._current_point
        painter.setPen(QPen(QColor(255, 255, 255), 1))
        painter.setBrush(QBrush(QColor(255, 255, 255, 120)))
        painter.drawEllipse(QPointF(cx, cy), 4, 4)


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Chaos Game")
        self.resize(980, 680)

        self._canvas = ChaosCanvas()
        self._running = False
        self._traversing = False

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._on_timer_tick)

        self._index_spinboxes: List[QSpinBox] = []
        self._build_ui()
        self._canvas.step_requested.connect(self._on_step_requested)
        self._canvas.vertex_indices_changed.connect(self._rebuild_vertex_index_controls)
        self._canvas.set_vertex_count(3)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        controls = QVBoxLayout()
        controls.setSpacing(10)

        params_group = QGroupBox("Parameters")
        form = QFormLayout(params_group)

        self._vertex_spin = QSpinBox()
        self._vertex_spin.setRange(2, 12)
        self._vertex_spin.setValue(3)
        self._vertex_spin.valueChanged.connect(self._on_vertex_count_changed)
        form.addRow("End points:", self._vertex_spin)

        self._fraction_spin = QDoubleSpinBox()
        self._fraction_spin.setRange(0.01, 2.0)
        self._fraction_spin.setSingleStep(0.05)
        self._fraction_spin.setDecimals(2)
        self._fraction_spin.setValue(0.75)
        self._fraction_spin.valueChanged.connect(self._on_fraction_changed)
        form.addRow("Move fraction:", self._fraction_spin)

        self._traversing_check = QCheckBox("Traversing (step on key press)")
        self._traversing_check.setChecked(False)
        self._traversing_check.toggled.connect(self._on_traversing_toggled)
        form.addRow(self._traversing_check)

        controls.addWidget(params_group)

        index_group = QGroupBox("Vertex indices")
        index_outer = QVBoxLayout(index_group)
        index_scroll = QScrollArea()
        index_scroll.setWidgetResizable(True)
        index_scroll.setMaximumHeight(180)
        self._index_controls_host = QWidget()
        self._index_controls_layout = QFormLayout(self._index_controls_host)
        index_scroll.setWidget(self._index_controls_host)
        index_outer.addWidget(index_scroll)
        self._index_hint = QLabel("Each end point needs a unique index.")
        self._index_hint.setWordWrap(True)
        index_outer.addWidget(self._index_hint)
        controls.addWidget(index_group)

        run_group = QGroupBox("Run")
        run_layout = QVBoxLayout(run_group)

        self._run_button = QPushButton("Start")
        self._run_button.clicked.connect(self._toggle_running)
        run_layout.addWidget(self._run_button)

        reset_button = QPushButton("Reset points")
        reset_button.clicked.connect(self._reset_points)
        run_layout.addWidget(reset_button)

        controls.addWidget(run_group)

        help_group = QGroupBox("Help")
        help_layout = QVBoxLayout(help_group)
        help_label = QLabel(
            "Drag the green start point and orange numbered end points.\n"
            "Assign each end point an index below; links appear only\n"
            "between consecutive indices (e.g. 1-2, 4-5, but not 2-4).\n"
            "If random hits a missing index, the point shifts to the\n"
            "next connected graph while keeping vertex distance ratios.\n"
            "Fraction 0.75 moves three quarters toward the chosen end point.\n"
            "Traversing OFF: points generate continuously while running.\n"
            "Traversing ON: each key press adds one point while running.\n"
            "Dragging an end point shifts the pattern while preserving\n"
            "distance ratios to every end point."
        )
        help_label.setWordWrap(True)
        help_layout.addWidget(help_label)
        controls.addWidget(help_group)

        controls.addStretch(1)

        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout(status_group)
        self._status_label = QLabel("Ready")
        self._status_label.setWordWrap(True)
        status_layout.addWidget(self._status_label)
        controls.addWidget(status_group)

        root.addLayout(controls, 0)
        root.addWidget(self._canvas, 1)

    def _on_vertex_count_changed(self, count: int) -> None:
        self._canvas.set_vertex_count(count)
        self._rebuild_vertex_index_controls()
        self._update_status()

    def _rebuild_vertex_index_controls(self) -> None:
        while self._index_controls_layout.count():
            item = self._index_controls_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self._index_spinboxes.clear()
        vertices = self._canvas.vertices()

        for list_index, vertex in enumerate(vertices):
            spin = QSpinBox()
            spin.setRange(1, 99)
            spin.setValue(vertex.index)
            spin.setProperty("list_index", list_index)
            spin.valueChanged.connect(self._on_vertex_index_changed)
            self._index_spinboxes.append(spin)
            self._index_controls_layout.addRow(f"Point {list_index + 1}:", spin)

    def _on_vertex_index_changed(self, value: int) -> None:
        spin = self.sender()
        if not isinstance(spin, QSpinBox):
            return

        list_index = spin.property("list_index")
        if list_index is None:
            return

        if not self._canvas.set_vertex_index(int(list_index), value):
            vertices = self._canvas.vertices()
            if 0 <= int(list_index) < len(vertices):
                spin.blockSignals(True)
                spin.setValue(vertices[int(list_index)].index)
                spin.blockSignals(False)
            self._index_hint.setText("Indices must be unique.")
        else:
            self._index_hint.setText("Each end point needs a unique index.")
        self._update_status()

    def _on_fraction_changed(self, value: float) -> None:
        self._canvas.set_fraction(value)

    def _on_traversing_toggled(self, checked: bool) -> None:
        self._traversing = checked
        self._update_status()

    def _toggle_running(self) -> None:
        self._running = not self._running
        if self._running:
            self._run_button.setText("Stop")
            self._canvas.setFocus()
            if not self._traversing:
                self._timer.start()
        else:
            self._run_button.setText("Start")
            self._timer.stop()
        self._update_status()

    def _reset_points(self) -> None:
        self._canvas.clear_points()
        self._update_status()

    def _on_timer_tick(self) -> None:
        if self._traversing:
            return
        for _ in range(40):
            self._canvas.generate_next_point()
        self._update_status()

    def _on_step_requested(self) -> None:
        if self._running and self._traversing:
            self._canvas.generate_next_point()
            self._update_status()

    def _update_status(self) -> None:
        mode = "step (key press)" if self._traversing else "continuous"
        run_state = "running" if self._running else "stopped"
        point_count = len(self._canvas._chaos_points)
        self._status_label.setText(
            f"State: {run_state} | Mode: {mode} | Points: {point_count}"
        )


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
