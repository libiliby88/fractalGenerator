"""Chaos Game visualizer with Tkinter (alternate UI to chaos_game.py)."""

from __future__ import annotations

import math
import random
import tkinter as tk
from dataclasses import dataclass, field
from tkinter import ttk
from typing import List, Optional, Tuple

import numpy as np

Point = Tuple[float, float]

HIT_RADIUS = 14.0
VERTEX_RADIUS = 10.0
START_RADIUS = 9.0
CURRENT_RADIUS = 4.0
POINT_RADIUS = 1.6

BACKGROUND = "#121218"
POINT_COLOR = "#78d2ff"
LINK_COLOR = "#46465a"
VERTEX_FILL = "#ff8c28"
VERTEX_OUTLINE = "#ffb450"
VERTEX_TEXT = "#fff0dc"
START_FILL = "#46d278"
START_OUTLINE = "#78ffa0"
CURRENT_FILL = "#ffffff"


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
        dist = distance(point, component_centroid(component))
        if dist < best_distance:
            best_distance = dist
            best_index = index
    return best_index


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
    if ref.size != len(vertices) or np.any(ref < 1e-9):
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


def lerp_point(current: Point, target: Point, fraction: float) -> Point:
    return (
        current[0] + fraction * (target[0] - current[0]),
        current[1] + fraction * (target[1] - current[1]),
    )


class ChaosCanvas(tk.Canvas):
    """Interactive canvas for the chaos game."""

    def __init__(self, master: tk.Misc, on_step: callable, on_indices_changed: callable) -> None:
        super().__init__(
            master,
            width=640,
            height=480,
            background=BACKGROUND,
            highlightthickness=0,
        )
        self._on_step = on_step
        self._on_indices_changed = on_indices_changed

        self._vertices: List[Vertex] = []
        self._initial_point: Point = (320.0, 240.0)
        self._current_point: Point = self._initial_point
        self._chaos_points: List[ChaosPoint] = []
        self._fraction: float = 0.75
        self._pending_count: int = 3

        self._drag_target: Optional[str] = None
        self._drag_index: int = -1
        self._drag_offset: Point = (0.0, 0.0)
        self._vertices_before_drag: List[Vertex] = []

        self.bind("<Configure>", self._on_configure)
        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Motion>", self._on_hover)
        self.bind("<Key>", self._on_key)
        self.bind("<Button-1>", lambda _event: self.focus_set(), add="+")

    def vertices(self) -> List[Vertex]:
        return self._vertices

    def point_count(self) -> int:
        return len(self._chaos_points)

    def set_vertex_count(self, count: int) -> None:
        self._pending_count = count
        width = self.winfo_width()
        height = self.winfo_height()
        if width <= 1 or height <= 1:
            # Not mapped yet; the first <Configure> event will lay the vertices out.
            self._vertices = []
            return
        self._vertices = default_vertices(count, width, height)
        self._chaos_points.clear()
        self._current_point = self._initial_point
        self._on_indices_changed()
        self.redraw()

    def set_vertex_index(self, list_index: int, new_index: int) -> bool:
        if not (0 <= list_index < len(self._vertices)):
            return False

        for i, vertex in enumerate(self._vertices):
            if i != list_index and vertex.index == new_index:
                return False

        self._vertices[list_index].index = new_index
        self.redraw()
        return True

    def set_fraction(self, fraction: float) -> None:
        self._fraction = fraction

    def clear_points(self) -> None:
        self._chaos_points.clear()
        self._current_point = self._initial_point
        self.redraw()

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
            new_point = lerp_point(self._current_point, target_vertex.position(), self._fraction)

        dists = compute_distances(new_point, self._vertices)
        self._chaos_points.append(ChaosPoint(new_point[0], new_point[1], dists))
        self._current_point = new_point
        return True

    def _on_configure(self, event: tk.Event) -> None:
        self._initial_point = (event.width / 2.0, event.height / 2.0)
        if not self._vertices:
            self.set_vertex_count(self._pending_count)
            return
        self._current_point = self._initial_point
        self.redraw()

    def _hit_test(self, pos: Point) -> Tuple[Optional[str], int]:
        if distance(pos, self._initial_point) <= HIT_RADIUS:
            return "initial", -1

        for index, vertex in enumerate(self._vertices):
            if distance(pos, vertex.position()) <= HIT_RADIUS:
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

        ref_dists = compute_distances(self._current_point, self._vertices_before_drag)
        self._current_point = reposition_by_distance_ratios(
            ref_dists,
            self._vertices,
            self._current_point,
        )

    def _on_press(self, event: tk.Event) -> None:
        pos = (float(event.x), float(event.y))
        target, index = self._hit_test(pos)
        if target is None:
            return

        self._drag_target = target
        self._drag_index = index
        self._vertices_before_drag = [Vertex(v.x, v.y, v.index) for v in self._vertices]

        anchor = self._initial_point if target == "initial" else self._vertices[index].position()
        self._drag_offset = (pos[0] - anchor[0], pos[1] - anchor[1])

    def _on_drag(self, event: tk.Event) -> None:
        pos = (float(event.x), float(event.y))
        dx, dy = self._drag_offset

        if self._drag_target == "initial":
            self._initial_point = (pos[0] - dx, pos[1] - dy)
            self._current_point = self._initial_point
            self.redraw()
            return

        if self._drag_target == "vertex" and 0 <= self._drag_index < len(self._vertices):
            self._vertices[self._drag_index].set_position(pos[0] - dx, pos[1] - dy)
            self._sync_chaos_points_to_vertices()
            self.redraw()

    def _on_release(self, _event: tk.Event) -> None:
        self._drag_target = None
        self._drag_index = -1
        self._vertices_before_drag.clear()

    def _on_hover(self, event: tk.Event) -> None:
        if self._drag_target is not None:
            return
        target, _ = self._hit_test((float(event.x), float(event.y)))
        self.configure(cursor="hand2" if target is not None else "")

    def _on_key(self, _event: tk.Event) -> str:
        self._on_step()
        return "break"

    def redraw(self) -> None:
        self.delete("all")

        for chaos_point in self._chaos_points:
            self._draw_dot(chaos_point.x, chaos_point.y, POINT_RADIUS, POINT_COLOR, POINT_COLOR)

        for left, right in consecutive_vertex_links(self._vertices):
            self.create_line(
                left.x, left.y, right.x, right.y, fill=LINK_COLOR, dash=(4, 4), width=1
            )

        for vertex in self._vertices:
            self._draw_dot(vertex.x, vertex.y, VERTEX_RADIUS, VERTEX_FILL, VERTEX_OUTLINE, width=2)
            self.create_text(
                vertex.x,
                vertex.y,
                text=str(vertex.index),
                fill=VERTEX_TEXT,
                font=("Segoe UI", 9, "bold"),
            )

        ix, iy = self._initial_point
        self._draw_dot(ix, iy, START_RADIUS, START_FILL, START_OUTLINE, width=2)
        self.create_text(
            ix + 12, iy - 8, text="Start", fill="#b4ffc8", anchor="w", font=("Segoe UI", 9)
        )

        self._draw_current_point()

    def redraw_incremental(self, new_points: int) -> None:
        """Draw only the freshly generated points to keep animation smooth."""
        if new_points:
            for chaos_point in self._chaos_points[-new_points:]:
                self._draw_dot(chaos_point.x, chaos_point.y, POINT_RADIUS, POINT_COLOR, POINT_COLOR)
        self._draw_current_point()

    def _draw_current_point(self) -> None:
        self.delete("current")
        cx, cy = self._current_point
        self._draw_dot(cx, cy, CURRENT_RADIUS, CURRENT_FILL, CURRENT_FILL, tags="current")

    def _draw_dot(
        self,
        x: float,
        y: float,
        radius: float,
        fill: str,
        outline: str,
        width: int = 1,
        tags: str = "",
    ) -> int:
        return self.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            fill=fill,
            outline=outline,
            width=width,
            tags=tags,
        )


class MainWindow(tk.Tk):
    """Main application window."""

    TICK_MS = 16
    POINTS_PER_TICK = 40
    CONTROLS_WIDTH = 260

    def __init__(self) -> None:
        super().__init__()
        self.title("Chaos Game (Tkinter)")
        self.geometry("980x680")

        self._running = False
        self._traversing = tk.BooleanVar(value=False)
        self._tick_job: Optional[str] = None
        self._index_vars: List[tk.StringVar] = []

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        # Lay out vertices once the real canvas size is known.
        self.update_idletasks()
        self._canvas.set_vertex_count(3)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)

        controls = ttk.Frame(root, width=self.CONTROLS_WIDTH)
        controls.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        controls.grid_propagate(False)

        params = ttk.LabelFrame(controls, text="Parameters", padding=8)
        params.pack(fill="x", pady=(0, 10))

        ttk.Label(params, text="End points:").grid(row=0, column=0, sticky="w", pady=2)
        self._vertex_spin = ttk.Spinbox(
            params, from_=2, to=12, width=6, command=self._on_vertex_count_changed
        )
        self._vertex_spin.set(3)
        self._vertex_spin.grid(row=0, column=1, sticky="ew", pady=2)

        ttk.Label(params, text="Move fraction:").grid(row=1, column=0, sticky="w", pady=2)
        self._fraction_spin = ttk.Spinbox(
            params,
            from_=0.01,
            to=2.0,
            increment=0.05,
            format="%.2f",
            width=6,
            command=self._on_fraction_changed,
        )
        self._fraction_spin.set("0.75")
        self._fraction_spin.grid(row=1, column=1, sticky="ew", pady=2)
        self._fraction_spin.bind("<Return>", lambda _e: self._on_fraction_changed())
        self._fraction_spin.bind("<FocusOut>", lambda _e: self._on_fraction_changed())

        ttk.Checkbutton(
            params,
            text="Traversing (step on key press)",
            variable=self._traversing,
            command=self._on_traversing_toggled,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))

        index_group = ttk.LabelFrame(controls, text="Vertex indices", padding=8)
        index_group.pack(fill="x", pady=(0, 10))

        index_body = ttk.Frame(index_group)
        index_body.pack(fill="both", expand=True)

        index_canvas = tk.Canvas(index_body, width=200, height=150, highlightthickness=0)
        scrollbar = ttk.Scrollbar(index_body, orient="vertical", command=index_canvas.yview)
        self._index_host = ttk.Frame(index_canvas)
        self._index_host.bind(
            "<Configure>",
            lambda _e: index_canvas.configure(scrollregion=index_canvas.bbox("all")),
        )
        index_canvas.create_window((0, 0), window=self._index_host, anchor="nw")
        index_canvas.configure(yscrollcommand=scrollbar.set)
        index_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._index_hint = ttk.Label(
            index_group,
            text="Each end point needs a unique index.",
            wraplength=self.CONTROLS_WIDTH - 40,
        )
        self._index_hint.pack(fill="x", pady=(6, 0))

        run_group = ttk.LabelFrame(controls, text="Run", padding=8)
        run_group.pack(fill="x", pady=(0, 10))
        self._run_button = ttk.Button(run_group, text="Start", command=self._toggle_running)
        self._run_button.pack(fill="x", pady=2)
        ttk.Button(run_group, text="Reset points", command=self._reset_points).pack(
            fill="x", pady=2
        )

        status_group = ttk.LabelFrame(controls, text="Status", padding=8)
        status_group.pack(fill="x", side="bottom")
        self._status_label = ttk.Label(
            status_group, text="Ready", wraplength=self.CONTROLS_WIDTH - 40
        )
        self._status_label.pack(fill="x")

        help_group = ttk.LabelFrame(controls, text="Help", padding=8)
        help_group.pack(fill="both", expand=True, pady=(0, 10))
        ttk.Label(
            help_group,
            wraplength=self.CONTROLS_WIDTH - 40,
            justify="left",
            text=(
                "Drag the green start point and orange numbered end points. "
                "Assign each end point an index; links appear only between "
                "consecutive indices (e.g. 1-2, 4-5, but not 2-4). "
                "If random hits a missing index, the point shifts to the next "
                "connected graph while keeping vertex distance ratios. "
                "Fraction 0.75 moves three quarters toward the chosen end point. "
                "Traversing OFF: points generate continuously while running. "
                "Traversing ON: each key press on the canvas adds one point."
            ),
        ).pack(fill="both", expand=True)

        self._canvas = ChaosCanvas(
            root,
            on_step=self._on_step_requested,
            on_indices_changed=self._rebuild_vertex_index_controls,
        )
        self._canvas.grid(row=0, column=1, sticky="nsew")

    def _on_vertex_count_changed(self) -> None:
        try:
            count = int(self._vertex_spin.get())
        except ValueError:
            return
        self._canvas.set_vertex_count(count)
        self._update_status()

    def _rebuild_vertex_index_controls(self) -> None:
        for child in self._index_host.winfo_children():
            child.destroy()
        self._index_vars.clear()

        for list_index, vertex in enumerate(self._canvas.vertices()):
            ttk.Label(self._index_host, text=f"Point {list_index + 1}:").grid(
                row=list_index, column=0, sticky="w", padx=(0, 6), pady=2
            )
            var = tk.StringVar(value=str(vertex.index))
            spin = ttk.Spinbox(self._index_host, from_=1, to=99, width=5, textvariable=var)
            spin.configure(command=lambda i=list_index: self._on_vertex_index_changed(i))
            spin.bind("<Return>", lambda _e, i=list_index: self._on_vertex_index_changed(i))
            spin.bind("<FocusOut>", lambda _e, i=list_index: self._on_vertex_index_changed(i))
            spin.grid(row=list_index, column=1, pady=2)
            self._index_vars.append(var)

    def _on_vertex_index_changed(self, list_index: int) -> None:
        vertices = self._canvas.vertices()
        if not (0 <= list_index < len(vertices)):
            return

        var = self._index_vars[list_index]
        try:
            value = int(var.get())
        except ValueError:
            var.set(str(vertices[list_index].index))
            return

        if self._canvas.set_vertex_index(list_index, value):
            self._index_hint.configure(text="Each end point needs a unique index.")
        else:
            var.set(str(vertices[list_index].index))
            self._index_hint.configure(text="Indices must be unique.")
        self._update_status()

    def _on_fraction_changed(self) -> None:
        try:
            self._canvas.set_fraction(float(self._fraction_spin.get()))
        except ValueError:
            self._fraction_spin.set("0.75")
            self._canvas.set_fraction(0.75)

    def _on_traversing_toggled(self) -> None:
        if self._running:
            if self._traversing.get():
                self._stop_tick()
            else:
                self._start_tick()
        self._update_status()

    def _toggle_running(self) -> None:
        self._running = not self._running
        if self._running:
            self._run_button.configure(text="Stop")
            self._canvas.focus_set()
            if not self._traversing.get():
                self._start_tick()
        else:
            self._run_button.configure(text="Start")
            self._stop_tick()
        self._update_status()

    def _start_tick(self) -> None:
        if self._tick_job is None:
            self._tick_job = self.after(self.TICK_MS, self._on_tick)

    def _stop_tick(self) -> None:
        if self._tick_job is not None:
            self.after_cancel(self._tick_job)
            self._tick_job = None

    def _on_close(self) -> None:
        self._running = False
        self._stop_tick()
        self.destroy()

    def _reset_points(self) -> None:
        self._canvas.clear_points()
        self._update_status()

    def _on_tick(self) -> None:
        self._tick_job = None
        if not self._running or self._traversing.get():
            return

        generated = 0
        for _ in range(self.POINTS_PER_TICK):
            if self._canvas.generate_next_point():
                generated += 1
        self._canvas.redraw_incremental(generated)
        self._update_status()
        self._start_tick()

    def _on_step_requested(self) -> None:
        if self._running and self._traversing.get():
            if self._canvas.generate_next_point():
                self._canvas.redraw()
            self._update_status()

    def _update_status(self) -> None:
        mode = "step (key press)" if self._traversing.get() else "continuous"
        run_state = "running" if self._running else "stopped"
        self._status_label.configure(
            text=f"State: {run_state} | Mode: {mode} | Points: {self._canvas.point_count()}"
        )


def main() -> None:
    MainWindow().mainloop()


if __name__ == "__main__":
    main()
