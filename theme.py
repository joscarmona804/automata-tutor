"""
theme.py
--------
Pure-data color palettes for Automata Tutor.

This module has no dependency on Tkinter (or anything outside the standard
library). It just describes named themes as plain hex strings so the GUI can
restyle itself without any rendering logic living here.

Each ``Theme`` field maps one-to-one onto a color constant used by ``app.py``:
    bg, canvas_bg, state_fill, state_active, state_outline, start_color,
    accept_color, edge_color, text_color, panel_bg, accent
"""

from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass(frozen=True)
class Theme:
    """A full color palette. Every field is a ``#rrggbb`` hex string."""

    bg: str            # window / root background
    canvas_bg: str     # drawing canvas background
    state_fill: str    # fill color of a state circle
    state_active: str  # fill when a state is "active" during simulation
    state_outline: str # outline stroke of a state circle
    start_color: str   # start-state arrow / marker
    accept_color: str  # accepting-state inner ring
    edge_color: str    # transition arrows and labels
    text_color: str    # default foreground text
    panel_bg: str      # side/explain panel background
    accent: str        # highlights, headings, selected items


# --------------------------------------------------------------------------- #
# Palettes
# --------------------------------------------------------------------------- #
# "Midnight" reuses the exact hex values already baked into app.py so switching
# to it is visually identical to the app's original look.
THEMES: dict[str, "Theme"] = {
    # "Arcade" — vibrant synthwave vibe: deep indigo/near-black backgrounds,
    # electric magenta accent, cyan start, lime accept, warm amber active.
    # Text is near-white for strong contrast on both bg and panel_bg.
    "Arcade": Theme(
        bg="#140d26",
        canvas_bg="#1b1140",
        state_fill="#2e1f63",
        state_active="#ffb340",
        state_outline="#c7b8ff",
        start_color="#28e0e0",
        accept_color="#8be34a",
        edge_color="#c7b8ff",
        text_color="#f4f0ff",
        panel_bg="#231652",
        accent="#ff3fd4",
    ),
    # "Bubblegum" — playful pastel light theme; dark ink text keeps AA contrast
    # on the soft pink/cream backgrounds while accents stay candy-bright.
    "Bubblegum": Theme(
        bg="#fff0f6",
        canvas_bg="#ffffff",
        state_fill="#ffe0ef",
        state_active="#ff8a3d",
        state_outline="#7a3b63",
        start_color="#0d8f9c",
        accept_color="#2f8f3a",
        edge_color="#5a3450",
        text_color="#2b1522",
        panel_bg="#ffe3f1",
        accent="#d61f8f",
    ),
    "Midnight": Theme(
        bg="#1e1f29",
        canvas_bg="#262732",
        state_fill="#3a3d52",
        state_active="#f6c177",
        state_outline="#c9cbe0",
        start_color="#9ccfd8",
        accept_color="#a6e3a1",
        edge_color="#c9cbe0",
        text_color="#e0def4",
        panel_bg="#2a2b38",
        accent="#c4a7e7",
    ),
    "Solarized": Theme(
        bg="#002b36",
        canvas_bg="#073642",
        state_fill="#094a56",
        state_active="#b58900",
        state_outline="#93a1a1",
        start_color="#2aa198",
        accept_color="#859900",
        edge_color="#93a1a1",
        text_color="#eee8d5",
        panel_bg="#073642",
        accent="#268bd2",
    ),
    "Nord": Theme(
        bg="#2e3440",
        canvas_bg="#3b4252",
        state_fill="#434c5e",
        state_active="#ebcb8b",
        state_outline="#d8dee9",
        start_color="#88c0d0",
        accept_color="#a3be8c",
        edge_color="#d8dee9",
        text_color="#eceff4",
        panel_bg="#3b4252",
        accent="#81a1c1",
    ),
    "Light": Theme(
        bg="#f4f5f7",
        canvas_bg="#ffffff",
        state_fill="#e2e6ef",
        state_active="#f0a202",
        state_outline="#4c566a",
        start_color="#1a7f94",
        accept_color="#2f7d32",
        edge_color="#3b4252",
        text_color="#1b1d23",
        panel_bg="#e9ebf0",
        accent="#6639a6",
    ),
}

DEFAULT_THEME = "Arcade"


def get_theme(name: str) -> Theme:
    """Return the theme named ``name``, or the default if it is unknown."""
    return THEMES.get(name, THEMES[DEFAULT_THEME])


# --------------------------------------------------------------------------- #
# Self-test
# --------------------------------------------------------------------------- #
def _is_hex_color(value: str) -> bool:
    if not isinstance(value, str) or len(value) != 7 or value[0] != "#":
        return False
    try:
        int(value[1:], 16)
    except ValueError:
        return False
    return True


def _channel_luminance(c: float) -> float:
    """Linearize a single 0..1 sRGB channel (per WCAG 2.x)."""
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _relative_luminance(hex_color: str) -> float:
    """Relative luminance (0..1) of a ``#rrggbb`` color, per WCAG 2.x."""
    r = int(hex_color[1:3], 16) / 255.0
    g = int(hex_color[3:5], 16) / 255.0
    b = int(hex_color[5:7], 16) / 255.0
    return (
        0.2126 * _channel_luminance(r)
        + 0.7152 * _channel_luminance(g)
        + 0.0722 * _channel_luminance(b)
    )


def _contrast_ratio(fg: str, bg: str) -> float:
    """WCAG contrast ratio between two colors (ranges 1.0 .. 21.0)."""
    l1 = _relative_luminance(fg)
    l2 = _relative_luminance(bg)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


# WCAG AA threshold for normal-size text.
AA_CONTRAST = 4.5


if __name__ == "__main__":
    assert DEFAULT_THEME in THEMES, "DEFAULT_THEME must name a real theme"
    for theme_name, theme in THEMES.items():
        print(theme_name)
        for f in fields(theme):
            color = getattr(theme, f.name)
            assert _is_hex_color(color), (
                f"{theme_name}.{f.name} = {color!r} is not a #rrggbb hex color"
            )
        # Text must stay readable on both the window and panel backgrounds.
        bg_ratio = _contrast_ratio(theme.text_color, theme.bg)
        panel_ratio = _contrast_ratio(theme.text_color, theme.panel_bg)
        print(f"  text/bg    contrast = {bg_ratio:.2f}:1")
        print(f"  text/panel contrast = {panel_ratio:.2f}:1")
        assert bg_ratio >= AA_CONTRAST, (
            f"{theme_name}: text_color vs bg contrast {bg_ratio:.2f} "
            f"< {AA_CONTRAST} (WCAG AA)"
        )
        assert panel_ratio >= AA_CONTRAST, (
            f"{theme_name}: text_color vs panel_bg contrast {panel_ratio:.2f} "
            f"< {AA_CONTRAST} (WCAG AA)"
        )
    assert get_theme("does-not-exist") is THEMES[DEFAULT_THEME]
    print(
        f"\nOK — {len(THEMES)} themes, all fields valid #rrggbb hex, "
        f"all text contrast >= {AA_CONTRAST}:1 (WCAG AA)."
    )
    print(f"Default theme: {DEFAULT_THEME}")
