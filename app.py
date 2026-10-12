"""
app.py
------
Automata Tutor — a gamified, JFLAP-style desktop app (Tkinter) that teaches
DFAs, NFAs, ε-transitions, regular expressions, and NFA→DFA conversion through
a concept-first campaign plus an exam-prep practice mode.

Grounded in Michael Sipser, *Introduction to the Theory of Computation*,
Chapter 1. All explanations are written in our own words.

Run with:   python app.py

Screens (all in one window, raised as needed)
---------------------------------------------
  HomeScreen      — pick a mode: Learn (campaign), Exam Prep, Cheat Sheets.
  CampaignScreen  — chapter map; each chapter opens a Lesson, then problems.
  LessonScreen    — concise teaching for a chapter + key ideas + worked example.
  PlayScreen      — the workspace: automaton canvas or regex editor, with
                    conversion source display and a subset-construction demo.
  ExamScreen      — timed mixed quiz (MCQ / true-false / membership) with
                    instant feedback and a weak-area summary.
  CheatScreen     — all chapter cheat sheets + exam tips in one place.

Only the Python standard library is used (Tkinter).
"""

from __future__ import annotations

import math
import os
import sys
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from typing import Dict, List, Optional, Tuple

from automaton import Automaton, EPSILON
from quiz import PROBLEMS, Problem, grade, get_problem, all_words
from regex_engine import regex_matches, RegexError
import curriculum
import game
import theme as themes
import lessons
import examprep


# ---------------------------------------------------------------------- #
# High-DPI / "HD" setup
# ---------------------------------------------------------------------- #
def enable_hidpi() -> None:
    """Mark the process per-monitor DPI aware on Windows for crisp rendering."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def resource_path(name: str) -> str:
    """Absolute path to a bundled resource (works under PyInstaller too)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


class ToolMode:
    ADD_STATE = "Add state"
    ADD_EDGE = "Add transition"
    MOVE = "Move / select"
    TOGGLE_START = "Mark start"
    TOGGLE_ACCEPT = "Mark accept"
    ERASE = "Erase"


# ====================================================================== #
# Root application
# ====================================================================== #
class AutomataTutor(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        # HD scaling
        try:
            dpi = self.winfo_fpixels("1i")
        except Exception:
            dpi = 96.0
        self.ui_scale = max(1.0, min(dpi / 96.0, 2.5))
        self.tk.call("tk", "scaling", dpi / 72.0)
        self.state_r = int(26 * self.ui_scale)
        self.accept_gap = max(4, int(5 * self.ui_scale))

        self.gs: game.GameState = game.load_progress()
        self.theme_name = tk.StringVar(value=themes.DEFAULT_THEME)
        self.T: themes.Theme = themes.get_theme(self.theme_name.get())

        self.title("Automata Tutor — learn DFAs, NFAs, ε, regex & conversions")
        self._set_window_icon()
        w, h = int(1320 * self.ui_scale), int(860 * self.ui_scale)
        self.geometry(f"{w}x{h}")
        self.minsize(int(1080 * self.ui_scale), int(720 * self.ui_scale))

        # Play-session bookkeeping (shared with PlayScreen).
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
        self._return_chapter: Optional[str] = None  # where "back" goes

        self._style = ttk.Style(self)
        try:
            self._style.theme_use("clam")
        except tk.TclError:
            pass

        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self._build_hud()
        self.container = tk.Frame(self)
        self.container.grid(row=1, column=0, sticky="nsew")
        self.container.rowconfigure(0, weight=1)
        self.container.columnconfigure(0, weight=1)

        self.home = HomeScreen(self.container, self)
        self.campaign = CampaignScreen(self.container, self)
        self.lesson = LessonScreen(self.container, self)
        self.play = PlayScreen(self.container, self)
        self.exam = ExamScreen(self.container, self)
        self.cheat = CheatScreen(self.container, self)
        for scr in (self.home, self.campaign, self.lesson, self.play,
                    self.exam, self.cheat):
            scr.grid(row=0, column=0, sticky="nsew")

        self.apply_theme()
        self.show_home()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ #
    # Window icon
    # ------------------------------------------------------------------ #
    def _set_window_icon(self) -> None:
        ico = resource_path("icon.ico")
        png = resource_path("icon.png")
        if sys.platform == "win32" and os.path.exists(ico):
            try:
                self.iconbitmap(default=ico)
            except tk.TclError:
                pass
        if os.path.exists(png):
            try:
                self._icon_image = tk.PhotoImage(file=png)
                self.iconphoto(True, self._icon_image)
            except tk.TclError:
                pass

    # ------------------------------------------------------------------ #
    # Theme
    # ------------------------------------------------------------------ #
    def apply_theme(self) -> None:
        T = self.T
        s = self._style
        self.configure(bg=T.bg)
        self.container.configure(bg=T.bg)

        base = ("Segoe UI", 10)
        head = ("Segoe UI Semibold", 13)
        s.configure("TFrame", background=T.bg)
        s.configure("TLabel", background=T.bg, foreground=T.text_color,
                    font=base)
        s.configure("Head.TLabel", background=T.bg, foreground=T.accent,
                    font=head)
        s.configure("Big.TLabel", background=T.bg, foreground=T.accent,
                    font=("Segoe UI Semibold", 20))
        s.configure("TButton", font=base, padding=6)
        s.configure("Accent.TButton", font=("Segoe UI Semibold", 11),
                    padding=8)
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
        for scr in (self.home, self.campaign, self.lesson, self.play,
                    self.exam, self.cheat):
            scr.restyle()

    def on_theme_change(self, *_a) -> None:
        self.T = themes.get_theme(self.theme_name.get())
        self.apply_theme()
        if self.current_problem and self.play.winfo_viewable():
            self.play.redraw()
        self.campaign.rebuild()

    # ------------------------------------------------------------------ #
    # HUD
    # ------------------------------------------------------------------ #
    def _build_hud(self) -> None:
        self.hud = tk.Frame(self, height=int(56 * self.ui_scale))
        self.hud.grid(row=0, column=0, sticky="ew")

        self.hud_home = ttk.Button(self.hud, text="⌂ Home",
                                   command=self.show_home)
        self.hud_home.pack(side="left", padx=(12, 6), pady=8)
        self.hud_level = tk.Label(self.hud, text="",
                                  font=("Segoe UI Semibold", 12))
        self.hud_level.pack(side="left", padx=8)

        self.xp_canvas = tk.Canvas(self.hud, width=int(200 * self.ui_scale),
                                   height=int(16 * self.ui_scale),
                                   highlightthickness=0, bd=0)
        self.xp_canvas.pack(side="left", padx=8)
        self.hud_xp_text = tk.Label(self.hud, text="", font=("Segoe UI", 9))
        self.hud_xp_text.pack(side="left", padx=(0, 12))
        self.hud_streak = tk.Label(self.hud, text="", font=("Segoe UI", 11))
        self.hud_streak.pack(side="left", padx=8)
        self.hud_stars = tk.Label(self.hud, text="", font=("Segoe UI", 11))
        self.hud_stars.pack(side="left", padx=8)

        self.theme_combo = ttk.Combobox(
            self.hud, state="readonly", width=11,
            values=list(themes.THEMES.keys()), textvariable=self.theme_name)
        self.theme_combo.pack(side="right", padx=12)
        self.theme_combo.bind("<<ComboboxSelected>>", self.on_theme_change)
        tk.Label(self.hud, text="Theme:", font=("Segoe UI", 10)).pack(
            side="right")
        self._xp_shown_fraction = 0.0

    def _refresh_hud(self) -> None:
        T = self.T
        lvl = self.gs.player_level()
        for lbl in (self.hud_level, self.hud_xp_text, self.hud_streak,
                    self.hud_stars):
            lbl.configure(bg=T.panel_bg, fg=T.text_color)
        self.hud_level.configure(text=f"★ Lv {lvl}", fg=T.accent)
        self.hud_streak.configure(
            text=f"🔥 {self.gs.current_streak} (best {self.gs.best_streak})")
        total_stars = sum(self.gs.per_problem_stars.values())
        self.hud_stars.configure(text=f"⭐ {total_stars}/{3 * len(PROBLEMS)}")

        floor = game._xp_for_level(lvl)
        nxt = game._xp_for_level(lvl + 1)
        span = max(1, nxt - floor)
        frac = max(0.0, min(1.0, (self.gs.total_xp - floor) / span))
        self.hud_xp_text.configure(
            text=f"{self.gs.total_xp} XP · {self.gs.xp_to_next_level()} to Lv "
                 f"{lvl + 1}")
        self._animate_xp_bar(frac)

    def _animate_xp_bar(self, target: float) -> None:
        T = self.T
        c = self.xp_canvas
        w, h = int(c.cget("width")), int(c.cget("height"))

        def draw(frac):
            c.delete("all")
            c.create_rectangle(0, 0, w, h, fill=T.canvas_bg, outline="")
            c.create_rectangle(0, 0, int(w * frac), h, fill=T.accent,
                               outline="")

        start = self._xp_shown_fraction
        steps = 14

        def step(i):
            if i > steps:
                self._xp_shown_fraction = target
                return
            draw(start + (target - start) * (i / steps))
            self.after(16, lambda: step(i + 1))
        step(0)

    # ------------------------------------------------------------------ #
    # Navigation
    # ------------------------------------------------------------------ #
    def show_home(self) -> None:
        self.home.rebuild()
        self.home.tkraise()
        self._pop()

    def show_campaign(self) -> None:
        self.campaign.rebuild()
        self.campaign.tkraise()
        self._pop()

    def show_lesson(self, chapter_id: str) -> None:
        self.lesson.load(chapter_id)
        self.lesson.tkraise()
        self._pop()

    def show_play(self, problem_key: str, return_chapter: Optional[str] = None
                  ) -> None:
        prob = get_problem(problem_key)
        if not prob:
            return
        if not self.gs.is_unlocked(problem_key):
            messagebox.showinfo("Locked", "Finish more of the earlier chapters "
                                          "to unlock this one.")
            return
        self._return_chapter = return_chapter or prob.chapter
        self.play.load_problem(prob)
        self.play.tkraise()
        self._pop()

    def show_exam(self) -> None:
        self.exam.setup()
        self.exam.tkraise()
        self._pop()

    def show_cheat(self) -> None:
        self.cheat.rebuild()
        self.cheat.tkraise()
        self._pop()

    def back_from_play(self) -> None:
        if self._return_chapter:
            self.show_lesson(self._return_chapter)
        else:
            self.show_campaign()

    def _pop(self) -> None:
        try:
            self.attributes("-alpha", 0.93)
            self.after(10, lambda: self.attributes("-alpha", 1.0))
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    def _on_close(self) -> None:
        self.save()
        self.destroy()

    def save(self) -> None:
        try:
            game.save_progress(self.gs)
        except Exception:
            pass


# ====================================================================== #
# Home screen
# ====================================================================== #
class HomeScreen(tk.Frame):
    def __init__(self, parent, app: AutomataTutor) -> None:
        super().__init__(parent)
        self.app = app
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        self.title = ttk.Label(self, text="Automata Tutor", style="Big.TLabel")
        self.title.grid(row=0, column=0, pady=(40, 2))
        self.tag = ttk.Label(
            self, text="Learn DFAs, NFAs, ε-moves, regular expressions, and "
                       "NFA→DFA conversion — then quiz yourself.")
        self.tag.grid(row=1, column=0, pady=(0, 24))

        self.cards = tk.Frame(self)
        self.cards.grid(row=2, column=0)
        self._card_defs = [
            ("📚  Learn", "Work through the five chapters, concept first.",
             self.app.show_campaign),
            ("📝  Exam Prep", "Timed mixed quiz. Find your weak spots fast.",
             self.app.show_exam),
            ("⚡  Cheat Sheets", "Every key fact and exam tip, in one place.",
             self.app.show_cheat),
        ]
        self._cards: List[tk.Widget] = []

    def restyle(self) -> None:
        self.configure(bg=self.app.T.bg)
        self.cards.configure(bg=self.app.T.bg)
        self.rebuild()

    def rebuild(self) -> None:
        T = self.app.T
        for c in self._cards:
            c.destroy()
        self._cards.clear()
        for i, (title, desc, cmd) in enumerate(self._card_defs):
            card = tk.Frame(self.cards, bg=T.panel_bg, highlightthickness=2,
                            highlightbackground=T.accent)
            card.grid(row=0, column=i, padx=14, pady=10, sticky="n")
            tk.Label(card, text=title, bg=T.panel_bg, fg=T.accent,
                     font=("Segoe UI Semibold", 16)).pack(padx=22, pady=(18, 6))
            tk.Label(card, text=desc, bg=T.panel_bg, fg=T.text_color,
                     font=("Segoe UI", 10), wraplength=int(190 * self.app.ui_scale),
                     justify="center").pack(padx=22, pady=(0, 14))
            btn = tk.Button(card, text="Open", command=cmd, relief="flat",
                            bg=T.accent, fg=T.bg,
                            activebackground=T.start_color,
                            font=("Segoe UI Semibold", 11), bd=0, padx=18,
                            pady=6, cursor="hand2")
            btn.pack(pady=(0, 18))
            self._cards.append(card)

        # progress line
        done = len(self.app.gs.solved)
        tk.Label  # noop to keep linter calm
        prog = ttk.Label(
            self.cards,
            text=f"Progress: {done}/{len(PROBLEMS)} problems solved · "
                 f"Level {self.app.gs.player_level()}")
        prog.grid(row=1, column=0, columnspan=3, pady=18)


# ====================================================================== #
# Campaign (chapter map) screen
# ====================================================================== #
class CampaignScreen(tk.Frame):
    def __init__(self, parent, app: AutomataTutor) -> None:
        super().__init__(parent)
        self.app = app
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self.header = ttk.Label(self, text="Campaign — five chapters",
                                style="Head.TLabel")
        self.header.grid(row=0, column=0, sticky="w", padx=20, pady=(16, 4))
        self.body = tk.Frame(self)
        self.body.grid(row=1, column=0, sticky="nsew", padx=12)
        self.body.columnconfigure(0, weight=1)

    def restyle(self) -> None:
        self.configure(bg=self.app.T.bg)
        self.body.configure(bg=self.app.T.bg)

    def rebuild(self) -> None:
        T = self.app.T
        for ch in self.body.winfo_children():
            ch.destroy()
        summaries = {s.chapter_id: s for s in self.app.gs.level_summary()}
        for row, chap in enumerate(curriculum.CHAPTERS):
            ts = summaries.get(chap.cid)
            if ts is None:
                continue
            unlocked = ts.unlocked
            card = tk.Frame(self.body, bg=T.panel_bg, highlightthickness=2,
                            highlightbackground=T.accent if unlocked
                            else T.canvas_bg)
            card.grid(row=row, column=0, sticky="ew", pady=7, padx=4)
            card.columnconfigure(1, weight=1)

            lock = "" if unlocked else "🔒 "
            tk.Label(card, text=f"{lock}{chap.title}", bg=T.panel_bg,
                     fg=T.accent if unlocked else T.text_color,
                     font=("Segoe UI Semibold", 14)).grid(
                row=0, column=0, sticky="w", padx=14, pady=(10, 0))
            tk.Label(card,
                     text=f"Solved {ts.solved}/{ts.total}   "
                          f"⭐ {ts.stars_earned}/{ts.stars_possible}",
                     bg=T.panel_bg, fg=T.text_color,
                     font=("Segoe UI", 10)).grid(row=0, column=1, sticky="e",
                                                 padx=14)
            tk.Label(card, text=chap.subtitle, bg=T.panel_bg,
                     fg=T.text_color, font=("Segoe UI", 10, "italic")).grid(
                row=1, column=0, columnspan=2, sticky="w", padx=14)

            btns = tk.Frame(card, bg=T.panel_bg)
            btns.grid(row=2, column=0, columnspan=2, sticky="w", padx=10,
                      pady=(6, 12))
            state = "normal" if unlocked else "disabled"
            tk.Button(btns, text="📖 Lesson + problems",
                      command=lambda c=chap.cid: self.app.show_lesson(c),
                      state=state, relief="flat",
                      bg=T.accent if unlocked else T.panel_bg,
                      fg=T.bg if unlocked else "#888",
                      activebackground=T.start_color,
                      font=("Segoe UI Semibold", 10), bd=0, padx=14, pady=6,
                      cursor="hand2" if unlocked else "arrow").pack(side="left")


# ====================================================================== #
# Lesson screen
# ====================================================================== #
class LessonScreen(tk.Frame):
    def __init__(self, parent, app: AutomataTutor) -> None:
        super().__init__(parent)
        self.app = app
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self.chapter_id = "dfa"

        top = tk.Frame(self)
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 4))
        self.back = ttk.Button(top, text="◂ Chapters",
                               command=self.app.show_campaign)
        self.back.pack(side="left")
        self.head = ttk.Label(top, text="", style="Head.TLabel")
        self.head.pack(side="left", padx=12)

        self.text = tk.Text(self, wrap="word", bd=0, highlightthickness=0,
                            padx=18, pady=14, cursor="arrow")
        self.text.grid(row=1, column=0, sticky="nsew", padx=16)
        self.text.configure(state="disabled")

        self.probframe = tk.Frame(self)
        self.probframe.grid(row=2, column=0, sticky="ew", padx=16,
                            pady=(6, 14))

    def restyle(self) -> None:
        T = self.app.T
        self.configure(bg=T.bg)
        self.probframe.configure(bg=T.bg)
        self.text.configure(bg=T.panel_bg, fg=T.text_color)
        self._tags()

    def _tags(self) -> None:
        T = self.app.T
        self.text.tag_configure("h", foreground=T.accent,
                                font=("Segoe UI Semibold", 13), spacing1=10,
                                spacing3=4)
        self.text.tag_configure("b", font=("Segoe UI", 11), spacing3=8)
        self.text.tag_configure("key", foreground=T.start_color,
                                font=("Segoe UI Semibold", 11))
        self.text.tag_configure("ex", foreground=T.accept_color,
                                font=("Consolas", 10))

    def load(self, chapter_id: str) -> None:
        self.chapter_id = chapter_id
        chap = curriculum.get_chapter(chapter_id)
        self.head.configure(text=chap.title)
        self._tags()
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", chap.subtitle + "\n", "b")
        for heading, body in chap.lesson:
            self.text.insert("end", f"\n{heading}\n", "h")
            self.text.insert("end", body + "\n", "b")
        # key ideas
        self.text.insert("end", "\nKey ideas\n", "h")
        for k in chap.key_ideas:
            self.text.insert("end", f"  ●  {k}\n", "key")
        # cheat sheet
        sheet = lessons.CHEAT_SHEETS.get(chapter_id, [])
        if sheet:
            self.text.insert("end", "\nQuick cheat sheet\n", "h")
            for line in sheet:
                self.text.insert("end", f"  •  {line}\n", "b")
        # worked example
        for we in lessons.WORKED_EXAMPLES.get(chapter_id, []):
            self.text.insert("end", f"\nWorked example — {we.title}\n", "h")
            self.text.insert("end", we.prompt + "\n", "b")
            for i, (hd, ex) in enumerate(we.steps, 1):
                self.text.insert("end", f"  {i}. {hd}\n", "key")
                self.text.insert("end", f"      {ex}\n", "b")
        self.text.configure(state="disabled")
        self.text.yview_moveto(0.0)
        self._build_problem_buttons(chapter_id)

    def _build_problem_buttons(self, chapter_id: str) -> None:
        T = self.app.T
        for ch in self.probframe.winfo_children():
            ch.destroy()
        tk.Label(self.probframe, text="Problems in this chapter:",
                 bg=T.bg, fg=T.text_color,
                 font=("Segoe UI Semibold", 11)).pack(anchor="w", pady=(0, 4))
        row = tk.Frame(self.probframe, bg=T.bg)
        row.pack(fill="x")
        probs = sorted([p for p in PROBLEMS if p.chapter == chapter_id],
                       key=lambda p: (p.order, p.difficulty))
        for p in probs:
            solved = p.key in self.app.gs.solved
            stars = self.app.gs.per_problem_stars.get(p.key, 0)
            label = ("✓ " if solved else "") + f"[{p.kind}] {p.title}"
            if solved:
                label += "  " + "★" * stars
            tk.Button(row, text=label, justify="left", anchor="w",
                      bg=T.canvas_bg, fg=T.text_color,
                      activebackground=T.accent, activeforeground=T.bg,
                      relief="flat", bd=0, padx=10, pady=6,
                      font=("Segoe UI", 9),
                      wraplength=int(220 * self.app.ui_scale), cursor="hand2",
                      command=lambda k=p.key, c=chapter_id:
                      self.app.show_play(k, c)).pack(
                side="left", padx=5, pady=4)


# ====================================================================== #
# Play (workspace) screen
# ====================================================================== #
class PlayScreen(tk.Frame):
    def __init__(self, parent, app: AutomataTutor) -> None:
        super().__init__(parent)
        self.app = app
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        # top bar
        top = tk.Frame(self)
        top.grid(row=0, column=0, columnspan=3, sticky="ew", padx=10,
                 pady=(8, 0))
        self.back = ttk.Button(top, text="◂ Back",
                               command=self.app.back_from_play)
        self.back.pack(side="left")
        self.prompt_label = ttk.Label(top, text="", style="Head.TLabel",
                                      wraplength=int(820 * app.ui_scale),
                                      justify="left")
        self.prompt_label.pack(side="left", padx=12)

        # left sidebar
        self.left = tk.Frame(self, width=int(230 * app.ui_scale))
        self.left.grid(row=1, column=0, sticky="ns", padx=10, pady=10)
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
        for txt, cmd, style in [
                ("Clear canvas", self.clear_canvas, "TButton"),
                ("Simulate a word…", self.simulate_dialog, "TButton"),
                ("Hint", self.give_hint, "TButton"),
                ("Check my answer", self.check_answer, "Accent.TButton"),
                ("Show solution", self.show_solution, "TButton")]:
            ttk.Button(self.actions, text=txt, command=cmd, style=style).pack(
                fill="x", pady=2)
        # conversion demo button (only shown for convert problems)
        self.demo_btn = ttk.Button(self.left, text="▶ Watch subset construction",
                                   command=self.play_subset_demo)

        # center
        self.center = tk.Frame(self)
        self.center.grid(row=1, column=1, sticky="nsew", padx=6, pady=10)
        self.center.rowconfigure(1, weight=1)
        self.center.columnconfigure(0, weight=1)
        self.source_label = ttk.Label(self.center, text="", justify="left",
                                      wraplength=int(560 * app.ui_scale))
        self.source_label.grid(row=0, column=0, sticky="w")
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
                       command=lambda s=sym: self._insert_re(s)).pack(
                side="left", padx=1)

        # right
        self.right = tk.Frame(self, width=int(400 * app.ui_scale))
        self.right.grid(row=1, column=2, sticky="ns", padx=10, pady=10)
        self.right.grid_propagate(False)
        ttk.Label(self.right, text="Explain", style="Head.TLabel").pack(
            anchor="w")
        self.explain = tk.Text(self.right, width=48, height=22, wrap="word",
                               bd=0, highlightthickness=0, padx=10, pady=10)
        self.explain.pack(fill="both", expand=True, pady=(4, 8))
        self.explain.configure(state="disabled")
        ttk.Label(self.right, text="Step-by-step trace",
                  style="Head.TLabel").pack(anchor="w")
        self.steplog = tk.Text(self.right, width=48, height=12, wrap="word",
                               bd=0, highlightthickness=0, padx=10, pady=10)
        self.steplog.pack(fill="both", expand=True, pady=4)
        self.steplog.configure(state="disabled")

    def restyle(self) -> None:
        T = self.app.T
        for f in (self, self.left, self.tools_frame, self.actions,
                  self.center, self.re_frame, self.palette, self.right):
            f.configure(bg=T.bg)
        self.canvas.configure(bg=T.canvas_bg)
        self.source_label.configure(background=T.bg, foreground=T.start_color)
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

    # ---- load a problem ----
    def load_problem(self, prob: Problem) -> None:
        self.app.current_problem = prob
        self.app._hints_shown = 0
        self.app._had_wrong = False
        self.app._solved_this_visit = False
        self.clear_canvas(confirm=False)
        tag = f"[{curriculum.get_chapter(prob.chapter).cid.upper()} · {prob.kind}]"
        self.prompt_label.config(text=f"{tag}  {prob.prompt}")

        # conversion source display
        if prob.source_spec:
            self._show_source(prob)
        else:
            self.source_label.config(text="")

        # demo button only for convert chapter
        if prob.chapter == "convert":
            self.demo_btn.pack(fill="x", pady=(8, 0))
        else:
            self.demo_btn.pack_forget()

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
            self.tools_frame.pack(fill="x", pady=(2, 8), before=self.actions)

        self._write_concept(prob)
        self._set_log([("dim", "Build your answer, then press "
                               "'Check my answer'.\n")])

    def _show_source(self, prob: Problem) -> None:
        spec = prob.source_spec
        lines = []
        tr = ", ".join(f"{s}--{sym}-->{d}" for s, sym, d in spec["transitions"])
        lines.append(f"GIVEN {('NFA' )}:  states {{{', '.join(spec['states'])}}}, "
                     f"start {spec['start']}, accept {{{', '.join(spec.get('accept', []))}}}")
        lines.append(f"transitions: {tr}")
        target = prob.conversion_target or prob.kind
        lines.append(f"➡ Build an equivalent {target} on the canvas.")
        self.source_label.config(text="\n".join(lines))

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
            chunks.append(("dim", f"\n{prob.sipser_ref} (Sipser, Ch.1).\n"))
        self._set_explain(chunks)
        if prob.note:
            self._append_explain([("h", "\nWorth knowing\n"),
                                  ("", prob.note + "\n")])

    # ---- subset construction demo ----
    def play_subset_demo(self) -> None:
        prob = self.app.current_problem
        spec = prob.source_spec if prob else None
        if not spec:
            spec = lessons.SUBSET_CONSTRUCTION_DEMO
        try:
            res = lessons.run_subset_construction(spec)
        except Exception as e:
            self._append_section([("bad", f"Could not run demo: {e}\n")])
            return
        chunks = [("h", "Subset construction, step by step\n"),
                  ("", "Each DFA state is the SET of NFA states you could be "
                       "in. Start = ε-closure of the NFA start.\n\n")]

        def nm(s):
            return "{" + ",".join(s) + "}"
        chunks.append(("mono", f"start: {nm(res['start'])}\n\n"))
        for ds in res["dfa_states"]:
            acc = " (accepting)" if ds in res["accept"] else ""
            chunks.append(("ok" if acc else "mono", f"{nm(ds)}{acc}\n"))
            for sym in res["alphabet"]:
                tgt = res["transitions"].get((ds, sym))
                if tgt is not None:
                    chunks.append(("", f"   --{sym}-->  {nm(tgt)}\n"))
        chunks.append(("dim", "\nNo new subsets appear, so the DFA is "
                              "complete.\n"))
        self._append_section(chunks)

    # ---- hints ----
    def give_hint(self) -> None:
        prob = self.app.current_problem
        if not prob:
            return
        hints = list(prob.re_hints) or [
            ln for ln in prob.strategy.split("\n") if ln.strip()]
        if self.app._hints_shown >= len(hints):
            self._append_section([("dim", "No more hints — try 'Show "
                                          "solution' if stuck.\n")])
            return
        h = hints[self.app._hints_shown]
        self.app._hints_shown += 1
        self._append_section([("h", f"Hint {self.app._hints_shown}\n"),
                              ("", h + "\n"),
                              ("dim", "(Hints lower the stars you can earn.)\n")])

    # ---- text helpers ----
    def _set_explain(self, chunks):
        self.explain.configure(state="normal")
        self.explain.delete("1.0", "end")
        for tag, txt in chunks:
            self.explain.insert("end", txt, tag)
        self.explain.configure(state="disabled")

    def _append_explain(self, chunks):
        self.explain.configure(state="normal")
        for tag, txt in chunks:
            self.explain.insert("end", txt, tag)
        self.explain.see("end")
        self.explain.configure(state="disabled")

    def _append_section(self, chunks):
        self._append_explain([("dim", "\n" + "─" * 30 + "\n")])
        self._append_explain(chunks)

    def _set_log(self, chunks):
        self.steplog.configure(state="normal")
        self.steplog.delete("1.0", "end")
        for tag, txt in chunks:
            self.steplog.insert("end", txt, tag)
        self.steplog.configure(state="disabled")

    # ---- canvas interaction ----
    def _reset_transient(self):
        self.app._edge_source = None
        self.app._drag_target = None
        self.redraw()

    def _state_at(self, x, y):
        r = self.app.state_r
        for name, st in self.app.automaton.states.items():
            if (x - st.x) ** 2 + (y - st.y) ** 2 <= r ** 2:
                return name
        return None

    def _on_canvas_click(self, evt):
        x, y = evt.x, evt.y
        mode = self.app.tool.get()
        hit = self._state_at(x, y)
        aut = self.app.automaton
        if mode == ToolMode.ADD_STATE:
            if hit is None:
                self._add_state_at(x, y)
        elif mode == ToolMode.TOGGLE_START:
            if hit:
                now = not aut.states[hit].is_start
                for s in aut.states.values():
                    s.is_start = False
                aut.states[hit].is_start = now
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

    def _on_canvas_drag(self, evt):
        if self.app.tool.get() == ToolMode.MOVE and self.app._drag_target:
            st = self.app.automaton.states[self.app._drag_target]
            st.x, st.y = evt.x, evt.y
            self.redraw()

    def _on_canvas_release(self, _evt):
        self.app._drag_target = None

    def _add_state_at(self, x, y):
        name = f"q{self.app._state_counter}"
        self.app._state_counter += 1
        is_start = (len(self.app.automaton.states) == 0)
        self.app.automaton.add_state(name, x=x, y=y, is_start=is_start)
        self.redraw()

    def _prompt_edge(self, src, dst):
        prob = self.app.current_problem
        syms = sorted(prob.alphabet) if prob else ["0", "1"]
        ans = simpledialog.askstring(
            "Transition symbol",
            f"Label for {src} → {dst}?\n"
            f"One symbol from: {', '.join(syms + [EPSILON])}\n"
            f"(use {EPSILON} for epsilon; comma-separate multiple)",
            parent=self)
        if not ans:
            return
        for sym in ans.strip().split(","):
            sym = sym.strip()
            if sym:
                self.app.automaton.add_transition(src, sym, dst)
        self.redraw()

    def clear_canvas(self, confirm=True):
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

    # ---- drawing ----
    def redraw(self):
        self.canvas.delete("all")
        self._draw_edges()
        for name, st in self.app.automaton.states.items():
            self._draw_state(name, st)

    def _draw_state(self, name, st):
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
            self.canvas.create_line(x - r - 26, y, x - r, y, fill=T.start_color,
                                    width=2, arrow="last")
        self.canvas.create_text(x, y, text=name, fill=T.text_color,
                                font=("Segoe UI Semibold", 11))

    def _draw_edges(self):
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

    def _draw_arrow(self, s, d, label):
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

    def _draw_self_loop(self, s, label):
        T = self.app.T
        r = self.app.state_r
        x, y = s.x, s.y
        self.canvas.create_arc(x - r, y - r - r, x + r, y + r - r, start=250,
                               extent=200, style="arc", outline=T.edge_color,
                               width=2)
        self.canvas.create_line(x + 8, y - r - 6, x + 14, y - r + 2,
                                fill=T.edge_color, width=2, arrow="last",
                                arrowshape=(10, 12, 4))
        self.canvas.create_text(x, y - r - r - 6, text=label, fill=T.accent,
                                font=("Consolas", 11, "bold"))

    def _insert_re(self, sym):
        self.re_entry.insert("insert", sym)
        self.re_entry.focus_set()

    # ---- grading ----
    def check_answer(self):
        prob = self.app.current_problem
        if not prob:
            return
        correct = self._check_regex(prob) if prob.kind == "RE" \
            else self._check_automaton(prob)
        if correct is True:
            self._on_correct()
        elif correct is False:
            self._on_wrong()

    def _on_correct(self):
        if self.app._solved_this_visit:
            return
        self.app._solved_this_visit = True
        prob = self.app.current_problem
        outcome = self.app.gs.record_solve(
            prob.key, hints_used=self.app._hints_shown,
            had_wrong_attempt=self.app._had_wrong)
        self.app.save()
        self.app._refresh_hud()
        self._celebrate(outcome)

    def _on_wrong(self):
        self.app._had_wrong = True
        self.app.gs.record_wrong_attempt(self.app.current_problem.key)
        self.app._refresh_hud()

    def _celebrate(self, outcome: game.SolveOutcome):
        stars = "★" * outcome.stars + "☆" * (3 - outcome.stars)
        lines = [("h", "\n🎉 Solved!\n"),
                 ("ok", f"{stars}   +{outcome.xp_gained} XP\n")]
        if outcome.level_up:
            lines.append(("h", f"⬆ Level up! Now level "
                               f"{outcome.player_level}.\n"))
        newly = getattr(outcome, "newly_unlocked_chapters", None) or \
            getattr(outcome, "newly_unlocked", [])
        if newly:
            names = ", ".join(curriculum.get_chapter(c).title.split("·")[-1].strip()
                              if curriculum.get_chapter(c) else c
                              for c in newly)
            lines.append(("ok", f"🔓 New chapter unlocked: {names}!\n"))
        lines.append(("dim", "Back to the chapter to pick the next one.\n"))
        self._append_section(lines)
        self._confetti()

    def _confetti(self):
        """A quick celebratory flash of dots on the canvas (if visible)."""
        if not self.canvas.winfo_viewable():
            return
        T = self.app.T
        w = self.canvas.winfo_width() or 400
        h = self.canvas.winfo_height() or 300
        import random
        cols = [T.accent, T.start_color, T.accept_color, T.state_active]
        dots = []
        for _ in range(24):
            x = random.randint(20, max(21, w - 20))
            y = random.randint(10, max(11, h // 2))
            d = self.canvas.create_oval(x, y, x + 8, y + 8,
                                        fill=random.choice(cols), outline="")
            dots.append((d, random.uniform(2, 5)))

        def fall(step):
            if step > 18:
                for d, _ in dots:
                    self.canvas.delete(d)
                self.redraw()
                return
            for d, spd in dots:
                self.canvas.move(d, 0, spd * 3)
            self.after(40, lambda: fall(step + 1))
        fall(0)

    def _check_automaton(self, prob) -> Optional[bool]:
        self.app.automaton.alphabet = set(prob.alphabet)
        res = grade(prob, self.app.automaton)
        if res.structural_issues:
            chunks = [("bad", "Structural problems\n")]
            for s in res.structural_issues:
                chunks.append(("", f"• {s}\n"))
            chunks.append(("dim", "\n" + res.message + "\n"))
            self._append_section(chunks)
            return None
        if res.correct:
            self._append_section([("ok", "✓ Correct!\n"),
                                  ("", res.message + "\n")])
            return True
        self._append_section([("bad", "✗ Not quite.\n"),
                              ("", res.message + "\n\n"),
                              ("", "Watch the trace to see where it fails.\n")])
        if res.counterexample is not None:
            self._auto_trace("" if res.counterexample == "ε (empty string)"
                             else res.counterexample)
        return False

    def _check_regex(self, prob) -> Optional[bool]:
        pattern = self.re_entry.get().strip()
        if not pattern:
            self._append_section([("bad", "Enter a regular expression "
                                          "first.\n")])
            return None
        alpha = set(prob.alphabet)
        try:
            regex_matches(pattern, "", alpha)
        except RegexError as e:
            self._append_section([("bad", "Syntax error\n"), ("", str(e) + "\n"),
                                  ("dim", "Allowed: 0 1 | * ( ) ε\n")])
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
                self._append_section([("bad", "✗ Not quite.\n"),
                                      ("", f'On "{disp}" your expression '
                                           f"{yours}, but it should "
                                           f"{should}.\n")])
                return False
        self._append_section([("ok", "✓ Correct!\n"),
                              ("", "Matches the target language on every "
                                   "string up to length 7.\n")])
        return True

    # ---- simulation ----
    def simulate_dialog(self):
        prob = self.app.current_problem
        if prob and prob.kind == "RE":
            self._simulate_regex()
            return
        word = simpledialog.askstring(
            "Simulate", "Enter a word to run through your automaton\n"
                        "(blank = empty string ε):", parent=self)
        if word is None:
            return
        self._auto_trace(word.strip())

    def _auto_trace(self, word):
        prob = self.app.current_problem
        if prob:
            self.app.automaton.alphabet = set(prob.alphabet)
        sim = self.app.automaton.simulate(word)
        disp = word or "ε"
        chunks = [("h", f'Tracing "{disp}"\n')]
        if sim.error:
            chunks.append(("bad", sim.error + "\n"))
            self._set_log(chunks)
            self.app._highlight = set()
            self.redraw()
            return
        for step in sim.steps:
            if step.symbol:
                chunks.append(("mono", f"[{step.index}] read '{step.symbol}'\n"))
            else:
                chunks.append(("mono", f"[{step.index}] start\n"))
            chunks.append(("", f"    {step.note}\n"))
        chunks.append(("ok", "\nResult: ACCEPTED ✓\n") if sim.accepted
                      else ("bad", "\nResult: REJECTED ✗\n"))
        self._set_log(chunks)
        self._animate_trace(sim)

    def _animate_trace(self, sim):
        def show(i):
            if i >= len(sim.steps):
                return
            self.app._highlight = set(sim.steps[i].after)
            self.redraw()
            self.after(550, lambda: show(i + 1))
        if sim.steps:
            show(0)

    def _simulate_regex(self):
        prob = self.app.current_problem
        pattern = self.re_entry.get().strip()
        if not pattern:
            self._set_log([("bad", "Type a regular expression first.\n")])
            return
        word = simpledialog.askstring(
            "Test your regex", "Enter a word to test (blank = ε):",
            parent=self)
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
        self._set_log([("h", f'Testing "{disp}"\n'),
                      ("mono", f"Your regex: {'MATCH' if got else 'no match'}\n"),
                      ("mono", f"Target: {'in' if expected else 'not in'} the "
                               f"language\n\n"),
                      ("ok", "They agree ✓\n") if got == expected
                      else ("bad", "They disagree ✗ — not equivalent yet.\n")])

    def show_solution(self):
        prob = self.app.current_problem
        if not prob:
            return
        self.app._hints_shown = max(self.app._hints_shown, 3)
        if prob.kind == "RE":
            self._append_section([("h", "Reference solution\n"),
                                  ("mono", (prob.reference_regex or "") + "\n\n"),
                                  ("", prob.strategy + "\n")])
            self.re_entry.delete(0, "end")
            self.re_entry.insert(0, prob.reference_regex or "")
        else:
            self._append_section([("h", "Reference construction\n"),
                                  ("", prob.strategy + "\n\n"),
                                  ("dim", "Rebuild it on the canvas, then "
                                          "Check.\n")])


# ====================================================================== #
# Exam Prep screen
# ====================================================================== #
class ExamScreen(tk.Frame):
    def __init__(self, parent, app: AutomataTutor) -> None:
        super().__init__(parent)
        self.app = app
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self.session: Optional[examprep.ExamSession] = None
        self.idx = 0
        self._timer_job = None

        top = tk.Frame(self)
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=10)
        ttk.Button(top, text="⌂ Home", command=self.app.show_home).pack(
            side="left")
        self.head = ttk.Label(top, text="Exam Prep", style="Head.TLabel")
        self.head.pack(side="left", padx=12)
        self.timer = ttk.Label(top, text="")
        self.timer.pack(side="right")

        self.body = tk.Frame(self)
        self.body.grid(row=1, column=0, sticky="nsew", padx=16, pady=8)
        self.body.columnconfigure(0, weight=1)

    def restyle(self):
        T = self.app.T
        self.configure(bg=T.bg)
        self.body.configure(bg=T.bg)

    def setup(self):
        T = self.app.T
        self._cancel_timer()
        self.session = None
        for ch in self.body.winfo_children():
            ch.destroy()
        tk.Label(self.body, text="Timed mixed quiz", bg=T.bg, fg=T.accent,
                 font=("Segoe UI Semibold", 16)).pack(anchor="w", pady=(4, 2))
        tk.Label(self.body,
                 text="Questions span all five topics: definitions, "
                      "true/false, and accept-or-reject. Pick a length:",
                 bg=T.bg, fg=T.text_color, wraplength=int(600 * self.app.ui_scale),
                 justify="left").pack(anchor="w", pady=(0, 10))
        row = tk.Frame(self.body, bg=T.bg)
        row.pack(anchor="w")
        for n, mins in [(10, 5), (20, 10), (30, 15)]:
            tk.Button(row, text=f"{n} questions · {mins} min",
                      command=lambda n=n, m=mins: self.start(n, m * 60),
                      relief="flat", bg=T.accent, fg=T.bg,
                      activebackground=T.start_color, bd=0, padx=16, pady=8,
                      font=("Segoe UI Semibold", 11), cursor="hand2").pack(
                side="left", padx=6)
        tk.Button(row, text="Untimed practice (15 q)",
                  command=lambda: self.start(15, None), relief="flat",
                  bg=T.panel_bg, fg=T.text_color, bd=0, padx=16, pady=8,
                  font=("Segoe UI", 11), cursor="hand2").pack(side="left",
                                                              padx=6)

    def start(self, n, time_limit):
        self.session = examprep.ExamSession.mixed(n, time_limit=time_limit)
        self.idx = 0
        self._tick()
        self.show_question()

    def _tick(self):
        if not self.session:
            return
        rem = self.session.seconds_remaining()
        if rem is None:
            self.timer.config(text="Untimed")
        else:
            m, s = divmod(int(rem), 60)
            self.timer.config(text=f"⏱ {m:02d}:{s:02d}")
            if self.session.is_expired():
                self.show_results()
                return
        self._timer_job = self.after(500, self._tick)

    def _cancel_timer(self):
        if self._timer_job:
            try:
                self.after_cancel(self._timer_job)
            except Exception:
                pass
            self._timer_job = None

    def show_question(self):
        T = self.app.T
        for ch in self.body.winfo_children():
            ch.destroy()
        qs = self.session.questions
        if self.idx >= len(qs):
            self.show_results()
            return
        q = qs[self.idx]
        tk.Label(self.body,
                 text=f"Question {self.idx + 1} of {len(qs)}   ·   "
                      f"topic: {q.topic}", bg=T.bg, fg=T.start_color,
                 font=("Segoe UI Semibold", 11)).pack(anchor="w")
        tk.Label(self.body, text=q.stem, bg=T.bg, fg=T.text_color,
                 font=("Segoe UI", 13), wraplength=int(760 * self.app.ui_scale),
                 justify="left").pack(anchor="w", pady=(8, 12))
        self._choice_var = tk.IntVar(value=-1)
        for i, opt in enumerate(q.options):
            tk.Radiobutton(self.body, text=opt, value=i,
                           variable=self._choice_var, bg=T.bg, fg=T.text_color,
                           selectcolor=T.panel_bg, activebackground=T.bg,
                           font=("Segoe UI", 12), anchor="w",
                           wraplength=int(720 * self.app.ui_scale),
                           justify="left").pack(anchor="w", pady=3)
        self._fb = tk.Label(self.body, text="", bg=T.bg,
                            font=("Segoe UI", 11),
                            wraplength=int(760 * self.app.ui_scale),
                            justify="left")
        self._fb.pack(anchor="w", pady=10)
        btns = tk.Frame(self.body, bg=T.bg)
        btns.pack(anchor="w", pady=6)
        self._submit = tk.Button(btns, text="Submit", command=self._submit_q,
                                 relief="flat", bg=T.accent, fg=T.bg,
                                 activebackground=T.start_color, bd=0, padx=18,
                                 pady=6, font=("Segoe UI Semibold", 11),
                                 cursor="hand2")
        self._submit.pack(side="left", padx=4)
        self._next = tk.Button(btns, text="Next ▸", command=self._next_q,
                               relief="flat", bg=T.panel_bg, fg=T.text_color,
                               bd=0, padx=18, pady=6, font=("Segoe UI", 11),
                               state="disabled", cursor="hand2")
        self._next.pack(side="left", padx=4)

    def _submit_q(self):
        q = self.session.questions[self.idx]
        choice = self._choice_var.get()
        if choice < 0:
            self._fb.config(text="Pick an answer first.", fg="#eb6f92")
            return
        correct = self.session.answer(q.qid, choice)
        T = self.app.T
        if correct:
            self._fb.config(text="✓ Correct. " + q.explanation,
                            fg=T.accept_color)
        else:
            right = q.options[q.answer_index]
            self._fb.config(text=f"✗ Not quite. Answer: {right}. "
                                 f"{q.explanation}", fg="#eb6f92")
        self._submit.config(state="disabled")
        self._next.config(state="normal")

    def _next_q(self):
        self.idx += 1
        self.show_question()

    def show_results(self):
        self._cancel_timer()
        T = self.app.T
        for ch in self.body.winfo_children():
            ch.destroy()
        correct, total = self.session.score()
        pct = int(100 * correct / total) if total else 0
        tk.Label(self.body, text=f"Score: {correct}/{total}  ({pct}%)",
                 bg=T.bg, fg=T.accent,
                 font=("Segoe UI Semibold", 18)).pack(anchor="w", pady=(6, 10))
        tk.Label(self.body, text="By topic:", bg=T.bg, fg=T.text_color,
                 font=("Segoe UI Semibold", 12)).pack(anchor="w")
        for topic, (c, t) in self.session.summary_by_topic().items():
            tk.Label(self.body, text=f"   {topic}: {c}/{t}", bg=T.bg,
                     fg=T.text_color, font=("Segoe UI", 11)).pack(anchor="w")
        focus = examprep.recommended_focus(self.session)
        if focus:
            tk.Label(self.body,
                     text="Review these before the exam: " + ", ".join(focus),
                     bg=T.bg, fg=T.start_color,
                     font=("Segoe UI Semibold", 12),
                     wraplength=int(700 * self.app.ui_scale),
                     justify="left").pack(anchor="w", pady=10)
        row = tk.Frame(self.body, bg=T.bg)
        row.pack(anchor="w", pady=10)
        tk.Button(row, text="New quiz", command=self.setup, relief="flat",
                  bg=T.accent, fg=T.bg, bd=0, padx=16, pady=6,
                  font=("Segoe UI Semibold", 11), cursor="hand2").pack(
            side="left", padx=4)
        tk.Button(row, text="Study cheat sheets", command=self.app.show_cheat,
                  relief="flat", bg=T.panel_bg, fg=T.text_color, bd=0, padx=16,
                  pady=6, font=("Segoe UI", 11), cursor="hand2").pack(
            side="left", padx=4)


# ====================================================================== #
# Cheat sheet screen
# ====================================================================== #
class CheatScreen(tk.Frame):
    def __init__(self, parent, app: AutomataTutor) -> None:
        super().__init__(parent)
        self.app = app
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        top = tk.Frame(self)
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=10)
        ttk.Button(top, text="⌂ Home", command=self.app.show_home).pack(
            side="left")
        ttk.Label(top, text="Cheat sheets & exam tips",
                  style="Head.TLabel").pack(side="left", padx=12)
        self.text = tk.Text(self, wrap="word", bd=0, highlightthickness=0,
                            padx=18, pady=14, cursor="arrow")
        self.text.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 14))
        self.text.configure(state="disabled")

    def restyle(self):
        T = self.app.T
        self.configure(bg=T.bg)
        self.text.configure(bg=T.panel_bg, fg=T.text_color)
        self.text.tag_configure("h", foreground=T.accent,
                                font=("Segoe UI Semibold", 14), spacing1=10,
                                spacing3=4)
        self.text.tag_configure("b", font=("Segoe UI", 11), spacing3=4)
        self.text.tag_configure("tip", foreground=T.accept_color,
                                font=("Segoe UI", 11), spacing3=4)

    def rebuild(self):
        self.restyle()
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        for chap in curriculum.CHAPTERS:
            self.text.insert("end", f"\n{chap.title}\n", "h")
            for line in lessons.CHEAT_SHEETS.get(chap.cid, []):
                self.text.insert("end", f"  •  {line}\n", "b")
        self.text.insert("end", "\nExam-day tips\n", "h")
        for tip in lessons.EXAM_TIPS:
            self.text.insert("end", f"  ✓  {tip}\n", "tip")
        self.text.configure(state="disabled")
        self.text.yview_moveto(0.0)


def main() -> None:
    enable_hidpi()
    app = AutomataTutor()
    app.mainloop()


if __name__ == "__main__":
    main()
