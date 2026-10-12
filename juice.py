"""
juice.py
--------
Reusable "2.5D juice" rendering + animation helpers for a Tkinter ``Canvas``
automata game.

The goal of this module is to make flat *circles-and-arrows* finite-automaton
diagrams look polished and lively — drop shadows, faked radial gradients that
give state nodes a spherical pop, soft glow halos, curved edges with readable
label chips, spring-pop entrances, color pulses, a token that walks the
accepting path, and a little confetti burst — all **without any 3D engine or
extra dependency**. Standard library + Tkinter only.

Design rules
~~~~~~~~~~~~
* **No blocking loops.** Every animation is driven by an injected ``after_fn``
  (the caller passes ``widget.after``), so this module never touches the GUI
  event loop directly and stays pure/composable.
* **Deletion-safe.** Canvas items may be destroyed mid-animation; all
  ``itemconfigure``/``coords``/``scale`` calls are wrapped so a stale id raises
  no error (``tkinter.TclError`` / generic guards).
* **No app coupling.** Nothing here imports ``app``/``quiz``/``automaton``.
  Helpers take a ``tk.Canvas`` and explicit arguments only. Colors are plain
  ``#rrggbb`` hex strings (matching the fields on the theme object:
  ``bg, canvas_bg, state_fill, state_active, state_outline, start_color,
  accept_color, edge_color, text_color, panel_bg, accent``).

Public API
~~~~~~~~~~
Color math:      ``hex_to_rgb``, ``rgb_to_hex``, ``lerp_hex``, ``shade``
Drawing:         ``draw_state``, ``draw_edge``, ``draw_self_loop``
Easing:          ``ease_out_back``, ``ease_out_cubic``, ``ease_in_out``
Animation:       ``spring_pop``, ``pulse``, ``token_points``, ``move_token``,
                 ``confetti``
"""

from __future__ import annotations

import math
import random
import tkinter as tk
from typing import Callable, Optional, Sequence

__all__ = [
    "hex_to_rgb",
    "rgb_to_hex",
    "lerp_hex",
    "shade",
    "draw_state",
    "draw_edge",
    "draw_self_loop",
    "ease_out_back",
    "ease_out_cubic",
    "ease_in_out",
    "spring_pop",
    "pulse",
    "token_points",
    "move_token",
    "confetti",
    "AnimHandle",
]

# A callable with the signature of ``tkinter.Widget.after``:
# ``after(delay_ms, callback) -> after_id``.
AfterFn = Callable[..., object]

RGB = tuple[int, int, int]
Point = tuple[float, float]


# --------------------------------------------------------------------------- #
# Color math
# --------------------------------------------------------------------------- #
def hex_to_rgb(h: str) -> RGB:
    """Convert a ``#rrggbb`` (or ``rrggbb``) hex string to an ``(r, g, b)`` tuple.

    Args:
        h: A hex color such as ``"#1e1f29"``. A leading ``#`` is optional and
            case does not matter.

    Returns:
        A 3-tuple of integer channels, each in ``0..255``.
    """
    s = h.lstrip("#")
    if len(s) == 3:  # allow shorthand like "#abc"
        s = "".join(ch * 2 for ch in s)
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def rgb_to_hex(rgb: Sequence[float]) -> str:
    """Convert an ``(r, g, b)`` sequence to a ``#rrggbb`` hex string.

    Channels are rounded and clamped to ``0..255`` so arithmetic results
    (floats, slightly-out-of-range values) are always safe to render.

    Args:
        rgb: A sequence of three numbers (ints or floats).

    Returns:
        A ``#rrggbb`` hex color string.
    """
    r, g, b = (max(0, min(255, int(round(c)))) for c in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def lerp_hex(a: str, b: str, t: float) -> str:
    """Linearly blend two hex colors.

    Args:
        a: Start color (``t == 0`` returns this).
        b: End color (``t == 1`` returns this).
        t: Blend amount in ``0..1`` (clamped).

    Returns:
        The blended ``#rrggbb`` color.
    """
    t = max(0.0, min(1.0, t))
    ar, ag, ab = hex_to_rgb(a)
    br, bg, bb = hex_to_rgb(b)
    return rgb_to_hex(
        (ar + (br - ar) * t, ag + (bg - ag) * t, ab + (bb - ab) * t)
    )


def shade(h: str, factor: float) -> str:
    """Lighten or darken a hex color by multiplying each channel.

    Args:
        h: The base color.
        factor: Multiplier. ``< 1`` darkens, ``> 1`` lightens, ``1`` is a
            no-op. The factor itself is clamped to a sane ``0..3`` range and
            resulting channels are clamped to ``0..255``.

    Returns:
        The shaded ``#rrggbb`` color.
    """
    factor = max(0.0, min(3.0, factor))
    r, g, b = hex_to_rgb(h)
    return rgb_to_hex((r * factor, g * factor, b * factor))


# --------------------------------------------------------------------------- #
# Internal drawing helpers
# --------------------------------------------------------------------------- #
def _rounded_rect_points(
    x1: float, y1: float, x2: float, y2: float, radius: float
) -> list[float]:
    """Return a flat ``[x, y, ...]`` list approximating a rounded rectangle.

    Used for label "chips". The polygon is drawn smoothed so straight corner
    segments round off visually.
    """
    radius = min(radius, (x2 - x1) / 2.0, (y2 - y1) / 2.0)
    return [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
    ]


def _label_chip(
    cv: tk.Canvas,
    cx: float,
    cy: float,
    text: str,
    *,
    text_color: str,
    chip_fill: str,
    font: tuple[str, int, str] = ("Segoe UI", 10, "bold"),
) -> list[int]:
    """Draw a small rounded chip centered at ``(cx, cy)`` with ``text`` on top.

    Returns the ids of the chip background and the text, in draw order.
    """
    # Rough text sizing (Tk gives no cheap metrics without a font object).
    half_w = max(10.0, len(text) * 4.0 + 6.0)
    half_h = 10.0
    chip = cv.create_polygon(
        _rounded_rect_points(cx - half_w, cy - half_h, cx + half_w, cy + half_h, 7),
        fill=chip_fill,
        outline="",
        smooth=True,
    )
    label = cv.create_text(cx, cy, text=text, fill=text_color, font=font)
    return [chip, label]


# --------------------------------------------------------------------------- #
# State node
# --------------------------------------------------------------------------- #
def draw_state(
    cv: tk.Canvas,
    x: float,
    y: float,
    r: float,
    *,
    label: str,
    fill: str,
    outline: str,
    text_color: str,
    accept: bool = False,
    accept_color: Optional[str] = None,
    start: bool = False,
    start_color: Optional[str] = None,
    active: bool = False,
    active_color: Optional[str] = None,
    glow: bool = False,
    glow_color: Optional[str] = None,
) -> list[int]:
    """Draw a 2.5D-looking automaton state node.

    The node is built (back to front) from: an optional glow halo, a soft drop
    shadow, a faked radial gradient (concentric ovals from a lightened top to a
    darkened bottom giving a spherical sheen), a crisp outline, an optional
    inner accepting ring, an optional incoming start arrow, and the centered
    bold label.

    Args:
        cv: Target canvas.
        x, y: Center of the node.
        r: Radius.
        label: Text drawn in the center.
        fill: Base fill color (gradient is derived from it, unless ``active``).
        outline: Outline stroke color.
        text_color: Label color.
        accept: If true, draw a second inner ring (accepting state).
        accept_color: Ring color; defaults to ``outline``.
        start: If true, draw a short incoming arrow on the left.
        start_color: Start arrow color; defaults to ``outline``.
        active: If true, use ``active_color`` as the gradient base (simulation
            highlight).
        active_color: Base color when ``active``; defaults to ``fill``.
        glow: If true, draw a faint larger halo ring behind the node.
        glow_color: Halo color; defaults to ``outline``.

    Returns:
        The list of created canvas item ids, in draw order (typically ~6–10).
    """
    ids: list[int] = []
    base = active_color if (active and active_color) else fill

    # --- glow halo (farthest back) ---------------------------------------- #
    if glow:
        gc = glow_color or outline
        gr = r + 10
        ids.append(
            cv.create_oval(
                x - gr, y - gr, x + gr, y + gr,
                fill="",
                outline=shade(gc, 1.1),
                width=6,
            )
        )

    # --- drop shadow ------------------------------------------------------- #
    # A darkened canvas-ish tone, offset down/right, slightly larger.
    shadow_col = shade(cv["background"] or "#000000", 0.55) \
        if cv["background"] else "#101018"
    off = max(3.0, r * 0.14)
    ids.append(
        cv.create_oval(
            x - r + off, y - r + off, x + r + off, y + r + off,
            fill=shadow_col,
            outline="",
        )
    )

    # --- faked radial gradient (spherical sheen) --------------------------- #
    # Stack a handful of concentric ovals, lightening toward the top-left.
    layers = 5
    top = shade(base, 1.25)
    bottom = shade(base, 0.8)
    for i in range(layers):
        t = i / (layers - 1)
        col = lerp_hex(top, bottom, t)
        # Shrink each layer and nudge its center downward so the lit area
        # sits near the top — a cheap specular highlight.
        shrink = (r * 0.9) * t
        cy_off = (r * 0.18) * t
        ids.append(
            cv.create_oval(
                x - r + shrink, y - r + shrink + cy_off,
                x + r - shrink, y + r - shrink + cy_off,
                fill=col,
                outline="",
            )
        )

    # --- crisp outline ----------------------------------------------------- #
    ids.append(
        cv.create_oval(
            x - r, y - r, x + r, y + r,
            fill="",
            outline=outline,
            width=2,
        )
    )

    # --- accepting inner ring --------------------------------------------- #
    if accept:
        ac = accept_color or outline
        ir = r - 5
        ids.append(
            cv.create_oval(
                x - ir, y - ir, x + ir, y + ir,
                fill="",
                outline=ac,
                width=2,
            )
        )

    # --- start arrow (incoming, on the left) ------------------------------ #
    if start:
        sc = start_color or outline
        ax0 = x - r - 22
        ax1 = x - r - 2
        ids.append(
            cv.create_line(
                ax0, y, ax1, y,
                fill=sc,
                width=3,
                arrow=tk.LAST,
                arrowshape=(10, 12, 5),
            )
        )

    # --- centered label ---------------------------------------------------- #
    ids.append(
        cv.create_text(
            x, y,
            text=label,
            fill=text_color,
            font=("Segoe UI", max(9, int(r * 0.6)), "bold"),
        )
    )
    return ids


# --------------------------------------------------------------------------- #
# Edges
# --------------------------------------------------------------------------- #
def draw_edge(
    cv: tk.Canvas,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    r: float,
    *,
    label: str,
    color: str,
    text_color: str,
    bidir_offset: float = 14,
    highlight: bool = False,
    highlight_color: Optional[str] = None,
) -> list[int]:
    """Draw a smooth curved arrow between two state nodes.

    The line is trimmed to start/end on the rims of the circles (radius ``r``),
    bowed sideways by ``bidir_offset`` so a reverse edge does not overlap it,
    capped with an arrowhead, and labeled with a rounded chip for readability.

    Args:
        cv: Target canvas.
        x1, y1: Source center.
        x2, y2: Target center.
        r: State radius (used to trim the endpoints to the rims).
        label: Transition label text.
        color: Line / arrow color.
        text_color: Label text color.
        bidir_offset: Sideways bow in pixels (perpendicular to the line).
        highlight: If true, draw thicker and brighter.
        highlight_color: Highlight color; defaults to a lightened ``color``.

    Returns:
        The list of created canvas item ids, in draw order.
    """
    ids: list[int] = []
    dx, dy = x2 - x1, y2 - y1
    dist = math.hypot(dx, dy) or 1.0
    ux, uy = dx / dist, dy / dist          # unit along the edge
    px, py = -uy, ux                       # unit perpendicular (for the bow)

    # Trim endpoints to the circle rims.
    sx, sy = x1 + ux * r, y1 + uy * r
    ex, ey = x2 - ux * r, y2 - uy * r

    # Control point: midpoint pushed sideways to create the curve.
    mx, my = (sx + ex) / 2.0, (sy + ey) / 2.0
    ctrl_x = mx + px * bidir_offset
    ctrl_y = my + py * bidir_offset

    line_col = (highlight_color or shade(color, 1.3)) if highlight else color
    width = 4 if highlight else 2

    ids.append(
        cv.create_line(
            sx, sy, ctrl_x, ctrl_y, ex, ey,
            fill=line_col,
            width=width,
            smooth=True,
            arrow=tk.LAST,
            arrowshape=(12, 14, 5),
            capstyle=tk.ROUND,
        )
    )

    # Label chip sits on the curve, nudged a bit further out than the control
    # point so it clears the line.
    lx = ctrl_x + px * (bidir_offset * 0.3)
    ly = ctrl_y + py * (bidir_offset * 0.3)
    chip_fill = shade(line_col, 0.35) if highlight else shade(color, 0.3)
    ids.extend(
        _label_chip(cv, lx, ly, label, text_color=text_color, chip_fill=chip_fill)
    )
    return ids


def draw_self_loop(
    cv: tk.Canvas,
    x: float,
    y: float,
    r: float,
    *,
    label: str,
    color: str,
    text_color: str,
    highlight: bool = False,
) -> list[int]:
    """Draw a self-transition loop sitting above a state node.

    Args:
        cv: Target canvas.
        x, y: Center of the state the loop belongs to.
        r: State radius.
        label: Transition label text.
        color: Loop / arrow color.
        text_color: Label text color.
        highlight: If true, draw thicker and brighter.

    Returns:
        The list of created canvas item ids, in draw order.
    """
    ids: list[int] = []
    line_col = shade(color, 1.3) if highlight else color
    width = 4 if highlight else 2

    # Loop arcs up and over the top of the node. Anchor on the upper rim,
    # bow out above with two control points, land back on the rim.
    top = y - r
    sx, sy = x - r * 0.5, top + r * 0.1
    ex, ey = x + r * 0.5, top + r * 0.1
    c1x, c1y = x - r * 0.9, top - r * 1.1
    c2x, c2y = x + r * 0.9, top - r * 1.1

    ids.append(
        cv.create_line(
            sx, sy, c1x, c1y, c2x, c2y, ex, ey,
            fill=line_col,
            width=width,
            smooth=True,
            arrow=tk.LAST,
            arrowshape=(10, 12, 5),
            capstyle=tk.ROUND,
        )
    )

    chip_fill = shade(color, 0.3)
    ids.extend(
        _label_chip(
            cv, x, top - r * 0.95, label,
            text_color=text_color, chip_fill=chip_fill,
        )
    )
    return ids


# --------------------------------------------------------------------------- #
# Easing
# --------------------------------------------------------------------------- #
def ease_out_back(t: float) -> float:
    """Overshoot easing: fast start, overshoots past 1, settles back.

    ``ease_out_back(0) == 0`` and ``ease_out_back(1) == 1`` exactly; values in
    between may exceed 1 (the "back" overshoot), which is what gives a spring a
    bit of bounce.
    """
    c1 = 1.70158
    c3 = c1 + 1.0
    u = t - 1.0
    return 1.0 + c3 * u * u * u + c1 * u * u


def ease_out_cubic(t: float) -> float:
    """Decelerating cubic easing. Maps ``0->0`` and ``1->1``."""
    u = 1.0 - t
    return 1.0 - u * u * u


def ease_in_out(t: float) -> float:
    """Smooth S-curve (quadratic in/out). Maps ``0->0`` and ``1->1``."""
    if t < 0.5:
        return 2.0 * t * t
    u = -2.0 * t + 2.0
    return 1.0 - (u * u) / 2.0


# --------------------------------------------------------------------------- #
# Animation handle
# --------------------------------------------------------------------------- #
class AnimHandle:
    """A tiny cancel-safe handle for an in-flight animation.

    Callers may hold onto this and call :meth:`cancel` to stop further frames
    from scheduling. The current pending frame may still fire once, but each
    frame checks ``cancelled`` before doing work.
    """

    __slots__ = ("cancelled",)

    def __init__(self) -> None:
        self.cancelled: bool = False

    def cancel(self) -> None:
        """Request cancellation; subsequent frames become no-ops."""
        self.cancelled = True


def _safe(fn: Callable[[], None]) -> None:
    """Run a canvas mutation, swallowing errors from already-deleted items."""
    try:
        fn()
    except tk.TclError:
        pass
    except Exception:  # noqa: BLE001 - belt-and-suspenders for stale ids
        pass


# --------------------------------------------------------------------------- #
# Spring pop (scale-in entrance)
# --------------------------------------------------------------------------- #
def spring_pop(
    cv: tk.Canvas,
    item_ids: Sequence[int],
    cx: float,
    cy: float,
    after_fn: AfterFn,
    *,
    duration_ms: int = 260,
    overshoot: float = 1.18,
) -> AnimHandle:
    """Animate freshly-created items "popping" in by scaling around a point.

    Items are scaled from near-zero up to full size using :func:`ease_out_back`
    so they overshoot slightly and settle — a springy entrance. Scaling is done
    incrementally with ``cv.scale`` (which multiplies), tracking the previous
    frame's scale so each frame applies only the delta.

    Args:
        cv: Target canvas.
        item_ids: Items to scale (e.g. the ids returned by :func:`draw_state`).
        cx, cy: The point to scale around (the node center).
        after_fn: ``widget.after``-style scheduler.
        duration_ms: Total animation length.
        overshoot: Peak scale factor fed into the easing's overshoot. Larger
            values exaggerate the bounce.

    Returns:
        An :class:`AnimHandle` that can cancel the animation.
    """
    handle = AnimHandle()
    frame_ms = 16
    frames = max(1, duration_ms // frame_ms)
    start_scale = 0.1

    # Shrink everything down first so it can grow back in.
    for iid in item_ids:
        _safe(lambda iid=iid: cv.scale(iid, cx, cy, start_scale, start_scale))

    state = {"i": 0, "prev": start_scale}

    def step() -> None:
        if handle.cancelled:
            return
        state["i"] += 1
        t = min(1.0, state["i"] / frames)
        # ease_out_back peaks slightly above 1; blend the overshoot in.
        eased = ease_out_back(t)
        target = 1.0 + (eased - 1.0) * max(0.0, (overshoot - 1.0) / 0.18 + 0.0)
        # Keep it well-behaved: target tracks eased toward 1.0.
        target = eased if overshoot <= 1.0 else eased
        factor = (target / state["prev"]) if state["prev"] else 1.0
        for iid in item_ids:
            _safe(lambda iid=iid, f=factor: cv.scale(iid, cx, cy, f, f))
        state["prev"] = target
        if t < 1.0 and not handle.cancelled:
            after_fn(frame_ms, step)
        else:
            # Snap exactly to 1.0 to kill accumulated float drift.
            if state["prev"]:
                corr = 1.0 / state["prev"]
                for iid in item_ids:
                    _safe(lambda iid=iid, f=corr: cv.scale(iid, cx, cy, f, f))

    after_fn(frame_ms, step)
    return handle


# --------------------------------------------------------------------------- #
# Color pulse
# --------------------------------------------------------------------------- #
def pulse(
    cv: tk.Canvas,
    item_ids: Sequence[int],
    after_fn: AfterFn,
    *,
    color_from: str,
    color_to: str,
    cycles: int = 2,
    duration_ms: int = 500,
) -> AnimHandle:
    """Pulse the outline/fill color of items between two colors.

    Each item's ``outline`` and ``fill`` are set (when present) to a color
    blended between ``color_from`` and ``color_to`` following a sine wave, for
    ``cycles`` full oscillations. Items that lack a given option simply ignore
    it (guarded).

    Args:
        cv: Target canvas.
        item_ids: Items to recolor.
        after_fn: ``widget.after``-style scheduler.
        color_from: Color at the trough of the pulse.
        color_to: Color at the crest of the pulse.
        cycles: Number of full oscillations.
        duration_ms: Total animation length.

    Returns:
        An :class:`AnimHandle` that can cancel the animation.
    """
    handle = AnimHandle()
    frame_ms = 16
    frames = max(1, duration_ms // frame_ms)
    state = {"i": 0}

    def apply_color(col: str) -> None:
        for iid in item_ids:
            _safe(lambda iid=iid: cv.itemconfigure(iid, outline=col))
            _safe(lambda iid=iid: cv.itemconfigure(iid, fill=col))

    def step() -> None:
        if handle.cancelled:
            return
        state["i"] += 1
        t = state["i"] / frames
        # Sine wave 0..1..0..1 across the requested number of cycles.
        wave = (1.0 - math.cos(t * cycles * 2.0 * math.pi)) / 2.0
        apply_color(lerp_hex(color_from, color_to, wave))
        if t < 1.0 and not handle.cancelled:
            after_fn(frame_ms, step)
        else:
            apply_color(color_from)  # settle back to the resting color

    after_fn(frame_ms, step)
    return handle


# --------------------------------------------------------------------------- #
# Token path + movement
# --------------------------------------------------------------------------- #
def token_points(
    path_coords: Sequence[Point],
    steps_per_seg: int = 18,
) -> list[Point]:
    """Densify a list of waypoints into eased points for a moving token.

    Given the centers of states a token visits during simulation, interpolate
    ``steps_per_seg`` eased points along each segment (using
    :func:`ease_in_out` so the token slows into and out of each node) and
    return the full flattened path.

    Args:
        path_coords: Ordered ``(x, y)`` waypoints (e.g. state centers).
        steps_per_seg: Interpolated points per segment.

    Returns:
        A dense list of ``(x, y)`` points. Returns the input (as a list) if it
        has fewer than two waypoints.
    """
    pts: list[Point] = []
    coords = list(path_coords)
    if len(coords) < 2:
        return coords
    for a, b in zip(coords, coords[1:]):
        (ax, ay), (bx, by) = a, b
        for s in range(steps_per_seg):
            t = ease_in_out(s / steps_per_seg)
            pts.append((ax + (bx - ax) * t, ay + (by - ay) * t))
    pts.append(coords[-1])  # make sure we land exactly on the final node
    return pts


def move_token(
    cv: tk.Canvas,
    token_id: int,
    pts: Sequence[Point],
    after_fn: AfterFn,
    *,
    frame_ms: int = 16,
    on_done: Optional[Callable[[], None]] = None,
) -> AnimHandle:
    """Animate an existing oval item along a precomputed list of points.

    The token (an oval created by the caller) is re-centered on each point in
    ``pts`` one frame at a time. ``on_done`` fires once the path completes (not
    if cancelled).

    Args:
        cv: Target canvas.
        token_id: Id of an existing oval item to move.
        pts: Points to walk through (see :func:`token_points`).
        after_fn: ``widget.after``-style scheduler.
        frame_ms: Delay between frames.
        on_done: Optional callback invoked after the last point.

    Returns:
        An :class:`AnimHandle` that can cancel the animation.
    """
    handle = AnimHandle()
    pts = list(pts)
    state = {"i": 0}

    # Figure out the token's half-size once so we can recenter via coords().
    try:
        x0, y0, x1, y1 = cv.coords(token_id)
        hw, hh = (x1 - x0) / 2.0, (y1 - y0) / 2.0
    except (tk.TclError, ValueError):
        hw = hh = 6.0

    def step() -> None:
        if handle.cancelled:
            return
        if state["i"] >= len(pts):
            if on_done is not None:
                on_done()
            return
        cx, cy = pts[state["i"]]
        _safe(lambda: cv.coords(token_id, cx - hw, cy - hh, cx + hw, cy + hh))
        state["i"] += 1
        after_fn(frame_ms, step)

    after_fn(frame_ms, step)
    return handle


# --------------------------------------------------------------------------- #
# Confetti
# --------------------------------------------------------------------------- #
def confetti(
    cv: tk.Canvas,
    after_fn: AfterFn,
    w: float,
    h: float,
    colors: Sequence[str],
    *,
    count: int = 24,
) -> AnimHandle:
    """Spawn a short confetti burst of falling colored dots, then clean up.

    Dots start near the top at random x positions, fall with a little gravity
    and horizontal drift, and are deleted when they leave the bottom (or when
    the whole burst finishes). Entirely self-contained and driven by
    ``after_fn``.

    Args:
        cv: Target canvas.
        after_fn: ``widget.after``-style scheduler.
        w, h: Canvas width and height (the play area).
        colors: Palette to pick dot colors from.
        count: Number of confetti dots.

    Returns:
        An :class:`AnimHandle` that can cancel the burst (and remove dots).
    """
    handle = AnimHandle()
    palette = list(colors) or ["#ffffff"]
    frame_ms = 16

    particles: list[dict[str, float]] = []
    for _ in range(count):
        px = random.uniform(0, w)
        py = random.uniform(-h * 0.2, 0)
        size = random.uniform(3, 6)
        col = random.choice(palette)
        iid = cv.create_oval(
            px, py, px + size, py + size, fill=col, outline=""
        )
        particles.append(
            {
                "id": iid,
                "x": px,
                "y": py,
                "size": size,
                "vx": random.uniform(-1.2, 1.2),
                "vy": random.uniform(1.5, 3.5),
            }
        )

    def cleanup() -> None:
        for p in particles:
            _safe(lambda p=p: cv.delete(int(p["id"])))

    def step() -> None:
        if handle.cancelled:
            cleanup()
            return
        alive = 0
        for p in particles:
            if p["y"] > h + 20:
                continue
            alive += 1
            p["vy"] += 0.12  # gravity
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            _safe(
                lambda p=p: cv.coords(
                    int(p["id"]),
                    p["x"], p["y"],
                    p["x"] + p["size"], p["y"] + p["size"],
                )
            )
        if alive > 0 and not handle.cancelled:
            after_fn(frame_ms, step)
        else:
            cleanup()

    after_fn(frame_ms, step)
    return handle
