"""
app.py
------
Automata Tutor — a gamified, JFLAP-style desktop app (Tkinter) that teaches
DFAs, NFAs, and regular expressions through a progressive campaign with XP,
stars, streaks, hints, themes, and step-by-step explanations.

Grounded in Michael Sipser, *Introduction to the Theory of Computation*,
Chapter 1 (regular languages). All explanations are written in our own words.

Run with:   python app.py

Architecture
------------
One window, two screens:
  * CampaignScreen — a map of difficulty tiers (levels) with locked/unlocked
    state, solved counts, and stars; this is the "beginning to end" spine.
  * PlayScreen — the workspace: an interactive automaton canvas (DFA/NFA) or a
    regular-expression editor, plus an Explain panel and a step-by-step trace.
A persistent HUD shows player level, an animated XP bar, streak, total stars,
and a theme picker.

Only the Python standard library is used (Tkinter).
"""

from __future__ import annotations

import math
import sys
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from typing import Dict, List, Optional, Tuple

from automaton import Automaton, EPSILON
from quiz import PROBLEMS, Problem, grade, get_problem, all_words
from regex_engine import regex_matches, RegexError
import game
import theme as themes


# ---------------------------------------------------------------------- #
# High-DPI / "HD" setup
# ---------------------------------------------------------------------- #
def enable_hidpi() -> None:
    """Mark the process per-monitor DPI aware on Windows for crisp rendering.

    Without this, Windows bitmap-stretches the window on high-DPI displays and
    everything looks blurry. Safe no-op elsewhere.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor aware
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


DIFFICULTY_NAMES = {
    1: "Warm-up",
    2: "Apprentice",
    3: "Journeyman",
    4: "Expert",
    5: "Master",
}


class ToolMode:
    ADD_STATE = "Add state"
    ADD_EDGE = "Add transition"
    MOVE = "Move / select"
    TOGGLE_START = "Mark start"
    TOGGLE_ACCEPT = "Mark accept"
    ERASE = "Erase"


class AutomataTutor(tk.Tk):
    # ================================================================== #
    # Construction
    # ================================================================== #
    def __init__(self) -> None:
        super().__init__()

        # --- HD scaling ---
        try:
            dpi = self.winfo_fpixels("1i")
        except Exception:
            dpi = 96.0
        self.ui_scale = max(1.0, min(dpi / 96.0, 2.5))
        self.tk.call("tk", "scaling", dpi / 72.0)
        self.state_r = int(26 * self.ui_scale)
        self.accept_gap = max(4, int(5 * self.ui_scale))

        # --- game state (persisted) ---
        self.gs: game.GameState = game.load_progress()

        # --- theme ---
        self.theme_name = tk.StringVar(value=themes.DEFAULT_THEME)
        self.T: themes.Theme = themes.get_theme(self.theme_name.get())

        self.title("Automata Tutor — learn DFAs, NFAs & regex by playing")
        w, h = int(1300 * self.ui_scale), int(840 * self.ui_scale)
        self.geometry(f"{w}x{h}")
        self.minsize(int(1060 * self.ui_scale), int(700 * self.ui_scale))

        # --- per-problem play session bookkeeping ---
        self.current_problem: Optional[Problem] = None
        self.automaton = Automaton()
        self.tool = tk.StringVar(value=ToolMode.ADD_STATE)
        self._state_counter = 0
        self._edge_source: Optional[str] = None
        self._drag_target: Optional[str] = None
        self._highlight: set = set()
        self._hints_shown = 0
        self._had_wrong = False
        self._solved_this_visit = False

        self._style = ttk.Style(self)
        try:
            self._style.theme_use("clam")
        except tk.TclError:
            pass

        # Root grid: HUD on top, screen container below.
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self._build_hud()
        self.container = tk.Frame(self)
        self.container.grid(row=1, column=0, sticky="nsew")
        self.container.rowconfigure(0, weight=1)
        self.container.columnconfigure(0, weight=1)

        self.campaign = CampaignScreen(self.container, self)
        self.play = PlayScreen(self.container, self)
        for scr in (self.campaign, self.play):
            scr.grid(row=0, column=0, sticky="nsew")

        self.apply_theme()
        self.show_campaign()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ================================================================== #
    # Theme handling
    # ================================================================== #
    def apply_theme(self) -> None:
        T = self.T
        s = self._style
        self.configure(bg=T.bg)
        self.container.configure(bg=T.bg)

        base = ("Segoe UI", int(10))
        head = ("Segoe UI Semibold", int(13))
        s.configure("TFrame", background=T.bg)
        s.configure("Card.TFrame", background=T.panel_bg)
        s.configure("TLabel", background=T.bg, foreground=T.text_color,
                    font=base)
        s.configure("Head.TLabel", background=T.bg, foreground=T.accent,
                    font=head)
        s.configure("Card.TLabel", background=T.panel_bg,
                    foreground=T.text_color, font=base)
        s.configure("CardHead.TLabel", background=T.panel_bg,
                    foreground=T.accent, font=head)
        s.configure("Hud.TLabel", background=T.panel_bg,
                    foreground=T.text_color, font=("Segoe UI Semibold", 11))
        s.configure("TButton", font=base, padding=6)
        s.configure("Accent.TButton", font=("Segoe UI Semibold", 10),
                    padding=6)
        s.configure("TRadiobutton", background=T.bg, foreground=T.text_color,
                    font=base)
        s.map("TRadiobutton", background=[("active", T.bg)])
        s.configure("TCombobox", fieldbackground=T.panel_bg,
                    background=T.panel_bg, foreground=T.text_color)

        self.hud.configure(bg=T.panel_bg)
        for child in self.hud.winfo_children():
            try:
                child.configure(bg=T.panel_bg)
            except tk.TclError:
                pass
        self._refresh_hud()
        self.campaign.restyle()
        self.play.restyle()

    def on_theme_change(self, *_a) -> None:
        self.T = themes.get_theme(self.theme_name.get())
        self.apply_theme()
        # Redraw whichever screen is live.
        if self.current_problem and self.play.winfo_viewable():
            self.play.redraw()
        self.campaign.rebuild()

    # ================================================================== #
    # HUD
    # ================================================================== #
    def _build_hud(self) -> None:
        self.hud = tk.Frame(self, height=int(56 * self.ui_scale))
        self.hud.grid(row=0, column=0, sticky="ew")
        self.hud.grid_propagate(True)

        self.hud_level = tk.Label(self.hud, text="", font=("Segoe UI Semibold",
                                  12))
        self.hud_level.pack(side="left", padx=(14, 8), pady=8)

        # XP bar (canvas so we can animate + theme it)
        self.xp_canvas = tk.Canvas(self.hud, width=int(220 * self.ui_scale),
                                   height=int(16 * self.ui_scale),
                                   highlightthickness=0, bd=0)
        self.xp_canvas.pack(side="left", padx=8)
        self.hud_xp_text = tk.Label(self.hud, text="", font=("Segoe UI", 9))
        self.hud_xp_text.pack(side="left", padx=(0, 14))

        self.hud_streak = tk.Label(self.hud, text="", font=("Segoe UI", 11))
        self.hud_streak.pack(side="left", padx=10)
        self.hud_stars = tk.Label(self.hud, text="", font=("Segoe UI", 11))
        self.hud_stars.pack(side="left", padx=10)

        # Right side: theme picker + map button
        self.theme_combo = ttk.Combobox(
            self.hud, state="readonly", width=12,
            values=list(themes.THEMES.keys()),
            textvariable=self.theme_name)
        self.theme_combo.pack(side="right", padx=12)
        self.theme_combo.bind("<<ComboboxSelected>>", self.on_theme_change)
        tk.Label(self.hud, text="Theme:", font=("Segoe UI", 10)).pack(
            side="right")
        self.map_btn = ttk.Button(self.hud, text="◂ Campaign map",
                                  command=self.show_campaign)
        self.map_btn.pack(side="right", padx=12)

        self._xp_shown_fraction = 0.0

    def _refresh_hud(self) -> None:
        T = self.T
        lvl = self.gs.player_level()
        self.hud_level.configure(
            text=f"★ Level {lvl}", bg=T.panel_bg, fg=T.accent)
        self.hud_xp_text.configure(bg=T.panel_bg, fg=T.text_color)
        self.hud_streak.configure(
            text=f"🔥 Streak {self.gs.current_streak}"
                 f"  (best {self.gs.best_streak})",
            bg=T.panel_bg, fg=T.text_color)
        total_stars = sum(self.gs.per_problem_stars.values())
        max_stars = 3 * len(PROBLEMS)
        self.hud_stars.configure(
            text=f"⭐ {total_stars}/{max_stars}", bg=T.panel_bg,
            fg=T.text_color)

        # XP bar target fraction within current level
        cur_lvl_floor = game._xp_for_level(lvl)
        nxt = game._xp_for_level(lvl + 1)
        span = max(1, nxt - cur_lvl_floor)
        frac = (self.gs.total_xp - cur_lvl_floor) / span
        frac = max(0.0, min(1.0, frac))
        self.hud_xp_text.configure(
            text=f"{self.gs.total_xp} XP · {self.gs.xp_to_next_level()} to next")
        self._animate_xp_bar(frac)

    def _animate_xp_bar(self, target: float) -> None:
        T = self.T
        c = self.xp_canvas
        w = int(c.cget("width"))
        h = int(c.cget("height"))

        def draw(frac: float) -> None:
            c.delete("all")
            c.create_rectangle(0, 0, w, h, fill=T.canvas_bg, outline="")
            c.create_rectangle(0, 0, int(w * frac), h, fill=T.accent,
                               outline="")

        start = self._xp_shown_fraction
        steps = 14

        def step(i: int) -> None:
            if i > steps:
                self._xp_shown_fraction = target
                return
            frac = start + (target - start) * (i / steps)
            draw(frac)
            self.after(16, lambda: step(i + 1))

        step(0)

    # ================================================================== #
    # Screen switching (with a quick fade-ish raise)
    # ================================================================== #
    def show_campaign(self) -> None:
        self.campaign.rebuild()
        self.map_btn.configure(state="disabled")
        self.campaign.tkraise()
        self._fade_in(self.campaign)

    def show_play(self, problem_key: str) -> None:
        prob = get_problem(problem_key)
        if not prob:
            return
        if not self.gs.is_unlocked(problem_key):
            messagebox.showinfo(
                "Locked",
                "That level is locked. Clear more of the earlier tiers to "
                "unlock it.")
            return
        self.map_btn.configure(state="normal")
        self.play.load_problem(prob)
        self.play.tkraise()
        self._fade_in(self.play)

    def _fade_in(self, widget) -> None:
        # Tk has no real per-widget alpha; emulate a subtle "pop" by nudging.
        try:
            self.attributes("-alpha", 0.92)
            self.after(10, lambda: self.attributes("-alpha", 1.0))
        except tk.TclError:
            pass

    # ================================================================== #
    # Persistence
    # ================================================================== #
    def _on_close(self) -> None:
        try:
            game.save_progress(self.gs)
        except Exception:
            pass
        self.destroy()

    def save(self) -> None:
        try:
            game.save_progress(self.gs)
        except Exception:
            pass


# ====================================================================== #
# Campaign (level map) screen
# ====================================================================== #
class CampaignScreen(tk.Frame):
    def __init__(self, parent, app: AutomataTutor) -> None:
        super().__init__(parent)
        self.app = app
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        self.header = ttk.Label(self, text="Campaign", style="Head.TLabel")
        self.header.grid(row=0, column=0, sticky="w", padx=20, pady=(16, 4))

        # Scrollable area for tiers
        self.body = tk.Frame(self)
        self.body.grid(row=1, column=0, sticky="nsew", padx=12)
        self.body.columnconfigure(0, weight=1)

        self.footer = tk.Frame(self)
        self.footer.grid(row=2, column=0, sticky="ew", padx=20, pady=10)
        self.reset_btn = ttk.Button(self.footer, text="Reset progress",
                                    command=self._reset)
        self.reset_btn.pack(side="right")
        self.tagline = ttk.Label(
            self.footer,
            text="Pick a level to play. Clear ~70% of a tier to unlock the "
                 "next.", style="TLabel")
        self.tagline.pack(side="left")

    def restyle(self) -> None:
        T = self.app.T
        self.configure(bg=T.bg)
        self.body.configure(bg=T.bg)
        self.footer.configure(bg=T.bg)

    def _reset(self) -> None:
        if messagebox.askyesno(
                "Reset progress",
                "Erase all XP, stars, and unlocks and start over?"):
            self.app.gs = game.reset_progress()
            self.app._refresh_hud()
            self.rebuild()

    def rebuild(self) -> None:
        T = self.app.T
        for child in self.body.winfo_children():
            child.destroy()

        summaries = self.app.gs.level_summary()
        row = 0
        for ts in summaries:
            if ts.total == 0:
                continue
            card = tk.Frame(self.body, bg=T.panel_bg, bd=0,
                            highlightthickness=1,
                            highlightbackground=T.accent if ts.unlocked
                            else T.canvas_bg)
            card.grid(row=row, column=0, sticky="ew", pady=7, padx=4)
            card.columnconfigure(1, weight=1)
            row += 1

            name = DIFFICULTY_NAMES.get(ts.difficulty, f"Tier {ts.difficulty}")
            lock = "" if ts.unlocked else "🔒 "
            title = tk.Label(
                card, text=f"{lock}Level {ts.difficulty} — {name}",
                bg=T.panel_bg, fg=T.accent if ts.unlocked else T.text_color,
                font=("Segoe UI Semibold", 13))
            title.grid(row=0, column=0, sticky="w", padx=14, pady=(10, 2))

            stats = tk.Label(
                card,
                text=f"Solved {ts.solved}/{ts.total}   "
                     f"⭐ {ts.stars_earned}/{ts.stars_possible}",
                bg=T.panel_bg, fg=T.text_color, font=("Segoe UI", 10))
            stats.grid(row=0, column=1, sticky="e", padx=14)

            # progress bar for this tier
            bar = tk.Canvas(card, height=int(8 * self.app.ui_scale),
                            bg=T.canvas_bg, highlightthickness=0, bd=0)
            bar.grid(row=1, column=0, columnspan=2, sticky="ew",
                     padx=14, pady=(2, 6))
            card.update_idletasks()

            def paint_bar(b=bar, frac=ts.solved_ratio):
                b.delete("all")
                w = b.winfo_width() or 400
                h = int(b.cget("height"))
                b.create_rectangle(0, 0, int(w * frac), h, fill=T.accept_color,
                                   outline="")
            bar.bind("<Configure>", lambda e, f=paint_bar: f())

            # problem chips
            chips = tk.Frame(card, bg=T.panel_bg)
            chips.grid(row=2, column=0, columnspan=2, sticky="w",
                       padx=10, pady=(0, 10))
            for p in [p for p in PROBLEMS if p.difficulty == ts.difficulty]:
                self._make_chip(chips, p, ts.unlocked)

    def _make_chip(self, parent, prob: Problem, tier_unlocked: bool) -> None:
        T = self.app.T
        solved = prob.key in self.app.gs.solved
        stars = self.app.gs.per_problem_stars.get(prob.key, 0)
        star_str = "★" * stars + "☆" * (3 - stars) if solved else ""
        kind_tag = f"[{prob.kind}]"
        label = f"{kind_tag} {prob.title}"
        if solved:
            label = "✓ " + label

        btn = tk.Button(
            parent, text=f"{label}\n{star_str}",
            justify="left", anchor="w",
            bg=T.canvas_bg if tier_unlocked else T.panel_bg,
            fg=T.text_color if tier_unlocked else "#777",
            activebackground=T.accent, activeforeground=T.bg,
            relief="flat", bd=0, padx=10, pady=6,
            font=("Segoe UI", 9), wraplength=int(200 * self.app.ui_scale),
            state="normal" if tier_unlocked else "disabled",
            command=lambda k=prob.key: self.app.show_play(k))
        btn.pack(side="left", padx=5, pady=4)


# ====================================================================== #
# Play (workspace) screen
# ====================================================================== #
class PlayScreen(tk.Frame):
    def __init__(self, parent, app: AutomataTutor) -> None:
        super().__init__(parent)
        self.app = app
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # ---- left sidebar: tools + actions ----
        self.left = tk.Frame(self, width=int(230 * app.ui_scale))
        self.left.grid(row=0, column=0, sticky="ns", padx=10, pady=10)

        self.tools_head = ttk.Label(self.left, text="Drawing tools",
                                    style="Head.TLabel")
        self.tools_head.pack(anchor="w")
        self.tools_frame = tk.Frame(self.left)
        self.tools_frame.pack(fill="x", pady=(2, 8))
        for mode in (ToolMode.ADD_STATE, ToolMode.ADD_EDGE, ToolMode.MOVE,
                     ToolMode.TOGGLE_START, ToolMode.TOGGLE_ACCEPT,
                     ToolMode.ERASE):
            ttk.Radiobutton(self.tools_frame, text=mode, value=mode,
                            variable=app.tool,
                            command=self._reset_transient).pack(anchor="w")

        self.actions = tk.Frame(self.left)
        self.actions.pack(fill="x", pady=6)
        ttk.Button(self.actions, text="Clear canvas",
                   command=self.clear_canvas).pack(fill="x", pady=2)
        ttk.Button(self.actions, text="Simulate a word…",
                   command=self.simulate_dialog).pack(fill="x", pady=2)
        ttk.Button(self.actions, text="Hint",
                   command=self.give_hint).pack(fill="x", pady=2)
        ttk.Button(self.actions, text="Check my answer",
                   style="Accent.TButton",
                   command=self.check_answer).pack(fill="x", pady=2)
        ttk.Button(self.actions, text="Show solution",
                   command=self.show_solution).pack(fill="x", pady=2)

        # ---- center: prompt + canvas / RE editor ----
        self.center = tk.Frame(self)
        self.center.grid(row=0, column=1, sticky="nsew", padx=6, pady=10)
        self.center.rowconfigure(1, weight=1)
        self.center.columnconfigure(0, weight=1)

        self.prompt_label = ttk.Label(self.center, text="",
                                      style="Head.TLabel",
                                      wraplength=int(560 * app.ui_scale),
                                      justify="left")
        self.prompt_label.grid(row=0, column=0, sticky="w", pady=(0, 6))

        self.canvas = tk.Canvas(self.center, highlightthickness=0, bd=0)
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)

        self.re_frame = tk.Frame(self.center)
        ttk.Label(self.re_frame, text="Your regular expression:").pack(
            anchor="w")
        self.re_entry = tk.Entry(self.re_frame, font=("Consolas", 16), bd=0,
                                 highlightthickness=2)
        self.re_entry.pack(fill="x", ipady=8, pady=6)
        self.palette = tk.Frame(self.re_frame)
        self.palette.pack(anchor="w", pady=2)
        for sym in ("0", "1", "(", ")", "|", "*", "ε"):
            ttk.Button(self.palette, text=sym, width=3,
                       command=lambda s=sym: self._insert_re(s)
                       ).pack(side="left", padx=1)

        # ---- right: explain + trace ----
        self.right = tk.Frame(self, width=int(380 * app.ui_scale))
        self.right.grid(row=0, column=2, sticky="ns", padx=10, pady=10)
        self.right.grid_propagate(False)

        ttk.Label(self.right, text="Explain", style="Head.TLabel").pack(
            anchor="w")
        self.explain = tk.Text(self.right, width=46, height=22, wrap="word",
                               bd=0, highlightthickness=0, padx=10, pady=10)
        self.explain.pack(fill="both", expand=True, pady=(4, 8))
        self.explain.configure(state="disabled")

        ttk.Label(self.right, text="Step-by-step trace",
                  style="Head.TLabel").pack(anchor="w")
        self.steplog = tk.Text(self.right, width=46, height=12, wrap="word",
                               bd=0, highlightthickness=0, padx=10, pady=10)
        self.steplog.pack(fill="both", expand=True, pady=4)
        self.steplog.configure(state="disabled")

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #
    def restyle(self) -> None:
        T = self.app.T
        for f in (self, self.left, self.tools_frame, self.actions,
                  self.center, self.re_frame, self.palette, self.right):
            f.configure(bg=T.bg)
        self.canvas.configure(bg=T.canvas_bg)
        self.re_entry.configure(bg=T.panel_bg, fg=T.text_color,
                                insertbackground=T.text_color,
                                highlightbackground=T.accent,
                                highlightcolor=T.accent)
        for txt, bg in ((self.explain, T.panel_bg), (self.steplog,
                                                     T.canvas_bg)):
            txt.configure(bg=bg, fg=T.text_color)
            self._config_text_tags(txt)

    def _config_text_tags(self, widget: tk.Text) -> None:
        T = self.app.T
        widget.tag_configure("h", foreground=T.accent,
                             font=("Segoe UI Semibold", 11), spacing1=6,
                             spacing3=3)
        widget.tag_configure("ok", foreground=T.accept_color,
                             font=("Segoe UI Semibold", 10))
        widget.tag_configure("bad", foreground="#eb6f92",
                             font=("Segoe UI Semibold", 10))
        widget.tag_configure("mono", font=("Consolas", 10))
        widget.tag_configure("dim", foreground="#9893a5")

    # ------------------------------------------------------------------ #
    # Load a problem into the workspace
    # ------------------------------------------------------------------ #
    def load_problem(self, prob: Problem) -> None:
        self.app.current_problem = prob
        self.app._hints_shown = 0
        self.app._had_wrong = False
        self.app._solved_this_visit = False
        self.clear_canvas(confirm=False)
        self.prompt_label.config(
            text=f"[Level {prob.difficulty} · {prob.kind}]  {prob.prompt}")

        if prob.kind == "RE":
            self.canvas.grid_remove()
            self.tools_head.pack_forget()
            self.tools_frame.pack_forget()
            self.re_frame.grid(row=1, column=0, sticky="new")
            self.re_entry.delete(0, "end")
            self.re_entry.focus_set()
        else:
            self.re_frame.grid_remove()
            self.canvas.grid(row=1, column=0, sticky="nsew")
            self.tools_head.pack(anchor="w", before=self.tools_frame)
            self.tools_frame.pack(fill="x", pady=(2, 8),
                                  before=self.actions)

        self._write_concept(prob)
        self._set_log([("dim", "Build your answer, then press "
                               "'Check my answer'.\n")])

    def _write_concept(self, prob: Problem) -> None:
        ex_a = ", ".join(f'"{w or "ε"}"' for w in prob.example_accept)
        ex_r = ", ".join(f'"{w or "ε"}"' for w in prob.example_reject)
        chunks = [
            ("h", f"{prob.title}\n"),
            ("", prob.concept + "\n\n"),
            ("h", "How to approach it\n"),
            ("", prob.strategy + "\n\n"),
            ("h", "Alphabet\n"),
            ("mono", "{" + ", ".join(prob.alphabet) + "}\n\n"),
            ("ok", "Should ACCEPT: "), ("", ex_a + "\n"),
            ("bad", "Should REJECT: "), ("", ex_r + "\n"),
        ]
        if prob.sipser_ref:
            chunks.append(("dim", f"\nReference: {prob.sipser_ref} "
                                  f"(Sipser, Intro to the Theory of "
                                  f"Computation).\n"))
        self._set_explain(chunks)
        if prob.note:
            self._append_explain([("h", "\nWorth knowing\n"),
                                  ("", prob.note + "\n")])

    # ------------------------------------------------------------------ #
    # Hints
    # ------------------------------------------------------------------ #
    def give_hint(self) -> None:
        prob = self.app.current_problem
        if not prob:
            return
        hints = list(prob.re_hints)
        if not hints:
            # Derive lightweight hints from the strategy for non-RE problems.
            hints = [line for line in prob.strategy.split("\n") if line.strip()]
        if self.app._hints_shown >= len(hints):
            self._append_section([("dim", "No more hints — try 'Show "
                                          "solution' if you're stuck.\n")])
            return
        h = hints[self.app._hints_shown]
        self.app._hints_shown += 1
        self._append_section([
            ("h", f"Hint {self.app._hints_shown}\n"),
            ("", h + "\n"),
            ("dim", "(Using hints lowers the stars you can earn.)\n"),
        ])

    # ------------------------------------------------------------------ #
    # Text helpers
    # ------------------------------------------------------------------ #
    def _set_explain(self, chunks: List[Tuple[str, str]]) -> None:
        self.explain.configure(state="normal")
        self.explain.delete("1.0", "end")
        for tag, txt in chunks:
            self.explain.insert("end", txt, tag)
        self.explain.configure(state="disabled")

    def _append_explain(self, chunks: List[Tuple[str, str]]) -> None:
        self.explain.configure(state="normal")
        for tag, txt in chunks:
            self.explain.insert("end", txt, tag)
        self.explain.see("end")
        self.explain.configure(state="disabled")

    def _append_section(self, chunks: List[Tuple[str, str]]) -> None:
        self._append_explain([("dim", "\n" + "─" * 30 + "\n")])
        self._append_explain(chunks)

    def _set_log(self, chunks: List[Tuple[str, str]]) -> None:
        self.steplog.configure(state="normal")
        self.steplog.delete("1.0", "end")
        for tag, txt in chunks:
            self.steplog.insert("end", txt, tag)
        self.steplog.configure(state="disabled")

    # ------------------------------------------------------------------ #
    # Canvas interaction (unchanged logic, theme-aware draw)
    # ------------------------------------------------------------------ #
    def _reset_transient(self) -> None:
        self.app._edge_source = None
        self.app._drag_target = None
        self.redraw()

    def _state_at(self, x: float, y: float) -> Optional[str]:
        r = self.app.state_r
        for name, st in self.app.automaton.states.items():
            if (x - st.x) ** 2 + (y - st.y) ** 2 <= r ** 2:
                return name
        return None

    def _on_canvas_click(self, evt) -> None:
        x, y = evt.x, evt.y
        mode = self.app.tool.get()
        hit = self._state_at(x, y)
        aut = self.app.automaton

        if mode == ToolMode.ADD_STATE:
            if hit is None:
                self._add_state_at(x, y)
        elif mode == ToolMode.TOGGLE_START:
            if hit:
                is_now = not aut.states[hit].is_start
                for s in aut.states.values():
                    s.is_start = False
                aut.states[hit].is_start = is_now
                self.redraw()
        elif mode == ToolMode.TOGGLE_ACCEPT:
            if hit:
                aut.states[hit].is_accept = not aut.states[hit].is_accept
                self.redraw()
        elif mode == ToolMode.ERASE:
            if hit:
                aut.remove_state(hit)
                self.redraw()
        elif mode == ToolMode.ADD_EDGE:
            if hit:
                if self.app._edge_source is None:
                    self.app._edge_source = hit
                    self.redraw()
                else:
                    self._prompt_edge(self.app._edge_source, hit)
                    self.app._edge_source = None
                    self.redraw()
        elif mode == ToolMode.MOVE:
            self.app._drag_target = hit

    def _on_canvas_drag(self, evt) -> None:
        if self.app.tool.get() == ToolMode.MOVE and self.app._drag_target:
            st = self.app.automaton.states[self.app._drag_target]
            st.x, st.y = evt.x, evt.y
            self.redraw()

    def _on_canvas_release(self, _evt) -> None:
        self.app._drag_target = None

    def _add_state_at(self, x: float, y: float) -> None:
        name = f"q{self.app._state_counter}"
        self.app._state_counter += 1
        is_start = (len(self.app.automaton.states) == 0)
        self.app.automaton.add_state(name, x=x, y=y, is_start=is_start)
        self.redraw()

    def _prompt_edge(self, src: str, dst: str) -> None:
        prob = self.app.current_problem
        syms = sorted(prob.alphabet) if prob else ["0", "1"]
        choices = ", ".join(syms + [EPSILON])
        ans = simpledialog.askstring(
            "Transition symbol",
            f"Label for {src} → {dst}?\n"
            f"Enter one symbol from: {choices}\n"
            f"(use {EPSILON} for an epsilon transition; comma-separate "
            f"multiple)",
            parent=self)
        if not ans:
            return
        for sym in ans.strip().split(","):
            sym = sym.strip()
            if sym:
                self.app.automaton.add_transition(src, sym, dst)
        self.redraw()

    def clear_canvas(self, confirm: bool = True) -> None:
        if confirm and self.app.automaton.states:
            if not messagebox.askyesno("Clear canvas",
                                       "Remove all states and transitions?"):
                return
        self.app.automaton = Automaton()
        if self.app.current_problem:
            self.app.automaton.alphabet = set(self.app.current_problem.alphabet)
        self.app._state_counter = 0
        self.app._edge_source = None
        self.app._highlight = set()
        self.redraw()

    # ------------------------------------------------------------------ #
    # Drawing
    # ------------------------------------------------------------------ #
    def redraw(self) -> None:
        self.canvas.delete("all")
        self._draw_edges()
        for name, st in self.app.automaton.states.items():
            self._draw_state(name, st)

    def _draw_state(self, name: str, st) -> None:
        T = self.app.T
        r = self.app.state_r
        x, y = st.x, st.y
        active = name in self.app._highlight
        fill = T.state_active if active else T.state_fill
        outline = T.start_color if name == self.app._edge_source \
            else T.state_outline
        width = 3 if name == self.app._edge_source else 2
        self.canvas.create_oval(x - r, y - r, x + r, y + r, fill=fill,
                                outline=outline, width=width)
        if st.is_accept:
            r2 = r - self.app.accept_gap
            self.canvas.create_oval(x - r2, y - r2, x + r2, y + r2,
                                    outline=T.accept_color, width=2)
        if st.is_start:
            self.canvas.create_line(x - r - 26, y, x - r, y,
                                    fill=T.start_color, width=2, arrow="last")
        self.canvas.create_text(x, y, text=name, fill=T.text_color,
                                font=("Segoe UI Semibold", 11))

    def _draw_edges(self) -> None:
        aut = self.app.automaton
        grouped: Dict[Tuple[str, str], List[str]] = {}
        for (src, sym), dsts in aut.transitions.items():
            for dst in dsts:
                grouped.setdefault((src, dst), []).append(sym)
        for (src, dst), syms in grouped.items():
            if src not in aut.states or dst not in aut.states:
                continue
            label = ",".join(sorted(syms))
            if src == dst:
                self._draw_self_loop(aut.states[src], label)
            else:
                self._draw_arrow(aut.states[src], aut.states[dst], label)

    def _draw_arrow(self, s, d, label: str) -> None:
        T = self.app.T
        r = self.app.state_r
        x1, y1, x2, y2 = s.x, s.y, d.x, d.y
        ang = math.atan2(y2 - y1, x2 - x1)
        sx, sy = x1 + r * math.cos(ang), y1 + r * math.sin(ang)
        ex, ey = x2 - r * math.cos(ang), y2 - r * math.sin(ang)
        mx = (sx + ex) / 2 + 14 * math.sin(ang)
        my = (sy + ey) / 2 - 14 * math.cos(ang)
        self.canvas.create_line(sx, sy, mx, my, ex, ey, smooth=True,
                                fill=T.edge_color, width=2, arrow="last",
                                arrowshape=(12, 14, 5))
        self.canvas.create_text(mx + 6 * math.sin(ang), my - 6 * math.cos(ang),
                                 text=label, fill=T.accent,
                                 font=("Consolas", 11, "bold"))

    def _draw_self_loop(self, s, label: str) -> None:
        T = self.app.T
        r = self.app.state_r
        x, y = s.x, s.y
        self.canvas.create_arc(x - r, y - r - r, x + r, y + r - r,
                               start=250, extent=200, style="arc",
                               outline=T.edge_color, width=2)
        self.canvas.create_line(x + 8, y - r - 6, x + 14, y - r + 2,
                                fill=T.edge_color, width=2, arrow="last",
                                arrowshape=(10, 12, 4))
        self.canvas.create_text(x, y - r - r - 6, text=label, fill=T.accent,
                                font=("Consolas", 11, "bold"))

    def _insert_re(self, sym: str) -> None:
        self.re_entry.insert("insert", sym)
        self.re_entry.focus_set()

    # ------------------------------------------------------------------ #
    # Grading
    # ------------------------------------------------------------------ #
    def check_answer(self) -> None:
        prob = self.app.current_problem
        if not prob:
            return
        if prob.kind == "RE":
            correct = self._check_regex(prob)
        else:
            correct = self._check_automaton(prob)
        if correct is True:
            self._on_correct()
        elif correct is False:
            self._on_wrong()

    def _on_correct(self) -> None:
        if self.app._solved_this_visit:
            return  # already credited this visit
        self.app._solved_this_visit = True
        prob = self.app.current_problem
        outcome = self.app.gs.record_solve(
            prob.key, hints_used=self.app._hints_shown,
            had_wrong_attempt=self.app._had_wrong)
        self.app.save()
        self.app._refresh_hud()
        self._celebrate(outcome)

    def _on_wrong(self) -> None:
        self.app._had_wrong = True
        prob = self.app.current_problem
        self.app.gs.record_wrong_attempt(prob.key)
        self.app._refresh_hud()

    def _celebrate(self, outcome: game.SolveOutcome) -> None:
        stars = "★" * outcome.stars + "☆" * (3 - outcome.stars)
        lines = [
            ("h", "\n🎉 Solved!\n"),
            ("ok", f"{stars}   +{outcome.xp_gained} XP\n"),
        ]
        if outcome.level_up:
            lines.append(("h", f"⬆ Level up! You're now level "
                               f"{outcome.player_level}.\n"))
        if outcome.newly_unlocked:
            names = ", ".join(DIFFICULTY_NAMES.get(d, f"Tier {d}")
                              for d in outcome.newly_unlocked)
            lines.append(("ok", f"🔓 New level unlocked: {names}!\n"))
        lines.append(("dim", "Head back to the campaign map to pick what's "
                             "next.\n"))
        self._append_section(lines)

    def _check_automaton(self, prob: Problem) -> Optional[bool]:
        self.app.automaton.alphabet = set(prob.alphabet)
        res = grade(prob, self.app.automaton)
        if res.structural_issues:
            chunks = [("bad", "Structural problems\n")]
            for s in res.structural_issues:
                chunks.append(("", f"• {s}\n"))
            chunks.append(("dim", "\n" + res.message + "\n"))
            self._append_section(chunks)
            return None  # not a scored wrong attempt — just incomplete
        if res.correct:
            self._append_section([
                ("ok", "✓ Correct!\n"),
                ("", res.message + "\n"),
            ])
            return True
        self._append_section([
            ("bad", "✗ Not quite.\n"),
            ("", res.message + "\n\n"),
            ("", "Watch the trace below to see where it goes wrong.\n"),
        ])
        if res.counterexample is not None:
            self._auto_trace("" if res.counterexample == "ε (empty string)"
                             else res.counterexample)
        return False

    def _check_regex(self, prob: Problem) -> Optional[bool]:
        pattern = self.re_entry.get().strip()
        if not pattern:
            self._append_section([("bad", "Enter a regular expression "
                                          "first.\n")])
            return None
        alpha = set(prob.alphabet)
        try:
            regex_matches(pattern, "", alpha)
        except RegexError as e:
            self._append_section([
                ("bad", "Syntax error in your expression\n"),
                ("", str(e) + "\n"),
                ("dim", "Allowed: 0, 1, | (union), * (star), parentheses, "
                        "ε.\n"),
            ])
            return None
        for w in all_words(prob.alphabet, 7):
            try:
                got = regex_matches(pattern, w, alpha)
            except RegexError as e:
                self._append_section([("bad", f"Error: {e}\n")])
                return None
            if got != prob.membership(w):
                disp = w or "ε (empty string)"
                should = "match" if prob.membership(w) else "not match"
                yours = "matches" if got else "does not match"
                self._append_section([
                    ("bad", "✗ Not quite.\n"),
                    ("", f'On "{disp}" your expression {yours}, but it '
                         f"should {should}.\n"),
                ])
                return False
        self._append_section([
            ("ok", "✓ Correct!\n"),
            ("", f'Your expression matches the target language on every '
                 f"string up to length 7.\n"),
        ])
        return True

    # ------------------------------------------------------------------ #
    # Simulation
    # ------------------------------------------------------------------ #
    def simulate_dialog(self) -> None:
        prob = self.app.current_problem
        if prob and prob.kind == "RE":
            self._simulate_regex()
            return
        word = simpledialog.askstring(
            "Simulate", "Enter a word to run through your automaton\n"
                        "(leave blank for the empty string ε):", parent=self)
        if word is None:
            return
        self._auto_trace(word.strip())

    def _auto_trace(self, word: str) -> None:
        prob = self.app.current_problem
        if prob:
            self.app.automaton.alphabet = set(prob.alphabet)
        sim = self.app.automaton.simulate(word)
        disp = word or "ε"
        chunks: List[Tuple[str, str]] = [("h", f'Tracing "{disp}"\n')]
        if sim.error:
            chunks.append(("bad", sim.error + "\n"))
            self._set_log(chunks)
            self.app._highlight = set()
            self.redraw()
            return
        for step in sim.steps:
            if step.symbol:
                chunks.append(("mono",
                               f"[{step.index}] read '{step.symbol}'\n"))
            else:
                chunks.append(("mono", f"[{step.index}] start\n"))
            chunks.append(("", f"    {step.note}\n"))
        chunks.append(("ok", "\nResult: ACCEPTED ✓\n") if sim.accepted
                      else ("bad", "\nResult: REJECTED ✗\n"))
        self._set_log(chunks)
        self._animate_trace(sim)

    def _animate_trace(self, sim) -> None:
        def show(i: int) -> None:
            if i >= len(sim.steps):
                return
            self.app._highlight = set(sim.steps[i].after)
            self.redraw()
            self.after(550, lambda: show(i + 1))
        if sim.steps:
            show(0)

    def _simulate_regex(self) -> None:
        prob = self.app.current_problem
        pattern = self.re_entry.get().strip()
        if not pattern:
            self._set_log([("bad", "Type a regular expression first.\n")])
            return
        word = simpledialog.askstring(
            "Test your regex",
            "Enter a word to test against your expression\n"
            "(blank = empty string ε):", parent=self)
        if word is None:
            return
        word = word.strip()
        try:
            got = regex_matches(pattern, word, set(prob.alphabet))
        except RegexError as e:
            self._set_log([("bad", f"Syntax error: {e}\n")])
            return
        expected = prob.membership(word)
        disp = word or "ε"
        self._set_log([
            ("h", f'Testing "{disp}"\n'),
            ("mono", f"Your regex: {'MATCH' if got else 'no match'}\n"),
            ("mono", f"Target language: {'in' if expected else 'not in'} "
                     f"the language\n\n"),
            ("ok", "They agree ✓\n") if got == expected
            else ("bad", "They disagree ✗ — not equivalent yet.\n"),
        ])

    # ------------------------------------------------------------------ #
    # Show solution
    # ------------------------------------------------------------------ #
    def show_solution(self) -> None:
        prob = self.app.current_problem
        if not prob:
            return
        # Looking at the solution counts like using every hint.
        self.app._hints_shown = max(self.app._hints_shown, 3)
        if prob.kind == "RE":
            self._append_section([
                ("h", "Reference solution\n"),
                ("mono", (prob.reference_regex or "") + "\n\n"),
                ("", prob.strategy + "\n"),
            ])
            self.re_entry.delete(0, "end")
            self.re_entry.insert(0, prob.reference_regex or "")
        else:
            self._append_section([
                ("h", "Reference construction\n"),
                ("", prob.strategy + "\n\n"),
                ("dim", "Rebuild it on the canvas, then press Check.\n"),
            ])


def main() -> None:
    enable_hidpi()
    app = AutomataTutor()
    app.mainloop()


if __name__ == "__main__":
    main()
