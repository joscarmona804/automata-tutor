"""
coach.py
--------
The *live coach*: pure logic that turns automaton-building into a play-first
experience by whispering short, in-the-moment nudges as the player works.

Design goals:
  * PLAY FIRST — every message is one short, friendly, imperative line.
  * REACTIVE — tips respond to what just happened (an event) against the
    automaton's real current state, not to a static script.
  * QUIET WHEN QUIET IS BEST — `react` returns None whenever there is
    nothing worth saying, so the coach never nags.

No GUI here. No tkinter. Standard library only. The UI layer decides when
to show a tip and may highlight `CoachTip.focus_state`.

The coach reads only the public surface of `Automaton` (states, transitions,
alphabet, start_state(), accept_states(), is_deterministic(), moves(),
simulate()) and `Problem` (kind, chapter, conversion_target, source_spec,
example_accept/reject, title).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from automaton import Automaton, EPSILON
from quiz import Problem


# Valid tones a CoachTip may carry. The UI maps these to colours/icons.
TONES = ("hint", "praise", "warn", "info", "goal")


@dataclass
class CoachTip:
    """A single bite-sized coaching message.

    Attributes:
        text:        The one-line nudge to show. Always non-empty.
        tone:        One of TONES ("hint", "praise", "warn", "info", "goal").
        focus_state: Optional state name the UI may highlight to draw the
                     player's eye to what the tip is talking about.
    """
    text: str
    tone: str
    focus_state: Optional[str] = None


# ---------------------------------------------------------------------- #
# Internal helpers
# ---------------------------------------------------------------------- #
def _pick(options: List[str], seed: Optional[int]) -> str:
    """Deterministically choose one line from `options`.

    `seed` indexes into the rotation (modulo its length) so wording varies
    without being random. `None` always yields the first option, keeping
    behaviour stable and testable.
    """
    if not options:
        return ""
    if seed is None:
        return options[0]
    return options[seed % len(options)]


def _missing_dfa_move(aut: Automaton) -> Optional[Tuple[str, str]]:
    """Return the first (state, symbol) a DFA still lacks a move on.

    Scans states and alphabet in a stable order so the same gap is reported
    consistently. Returns None if every state has a move on every symbol
    (i.e. the machine is total) or if there is no alphabet yet.
    """
    for name in aut.states:
        for sym in sorted(aut.alphabet):
            if not aut.moves(name, sym):
                return (name, sym)
    return None


def _nondeterministic_state(aut: Automaton) -> Optional[Tuple[str, str]]:
    """Return the first (state, symbol) with more than one outgoing move.

    This is legal for an NFA but breaks determinism for a DFA.
    """
    for name in aut.states:
        for sym in sorted(aut.alphabet):
            if len(aut.moves(name, sym)) > 1:
                return (name, sym)
    return None


def _structurally_complete(problem: Problem, aut: Automaton) -> bool:
    """True when the machine looks finished enough to try a Check.

    Requires a start state and at least one accept state. For DFA problems
    it additionally requires determinism (one move per state per symbol,
    no epsilon). NFA / RE / conversion-to-NFA problems only need start +
    accept to be considered 'ready to check'.
    """
    if aut.start_state() is None:
        return False
    if not aut.accept_states():
        return False
    if _wants_dfa(problem):
        is_dfa, _reasons = aut.is_deterministic()
        return is_dfa
    return True


def _wants_dfa(problem: Problem) -> bool:
    """True if the player is expected to produce a DFA for this problem."""
    if problem.kind == "DFA":
        return True
    return problem.conversion_target == "DFA"


# ---------------------------------------------------------------------- #
# 1. Opening nudge
# ---------------------------------------------------------------------- #
def opening_tip(problem: Problem) -> CoachTip:
    """Return a single playful 'here's your goal, go!' line for a problem.

    Tailored to the problem KIND / chapter: DFAs nudge toward dropping a
    start state, REs toward typing an expression, and conversions point at
    the given source machine. Deliberately ~one short sentence.
    """
    title = problem.title

    # Conversion tasks: point at the thing they must translate.
    if problem.conversion_target:
        target = problem.conversion_target
        if problem.source_spec:
            return CoachTip(
                text=f"Translate the given machine into a {target} — read it, then rebuild.",
                tone="goal",
            )
        return CoachTip(
            text=f"Turn the regex into a {target} — sketch it piece by piece.",
            tone="goal",
        )

    if problem.kind == "RE":
        return CoachTip(
            text=f"Goal: {title}. Type a pattern and watch it light up.",
            tone="goal",
        )

    if problem.kind == "NFA" or problem.chapter in ("nfa", "epsilon"):
        extra = " — ε edges are fair game." if problem.chapter == "epsilon" else ""
        return CoachTip(
            text=f"Goal: {title}. Guessing is allowed{extra} — drop a start state to begin.",
            tone="goal",
        )

    # Default: DFA.
    return CoachTip(
        text=f"Goal: {title}. Drop your first state — it's the start.",
        tone="goal",
    )


# ---------------------------------------------------------------------- #
# 2. The live reaction
# ---------------------------------------------------------------------- #
def react(problem: Problem,
          aut: Automaton,
          event: Dict[str, Any],
          seed: Optional[int] = None) -> Optional[CoachTip]:
    """React to a just-happened `event` against the current automaton.

    Returns a short contextual CoachTip, or None to stay quiet (the common
    case — the coach should not talk after every click).

    `event` is a small dict with a "type" key, e.g.
        {"type": "add_state", "name": "q0"}
        {"type": "add_edge", "src": "q0", "sym": "1", "dst": "q1"}
        {"type": "mark_start", "name": "q0"}
        {"type": "mark_accept", "name": "q1"}
        {"type": "erase", ...}
        {"type": "idle"}

    `seed` optionally rotates wording deterministically; None uses the
    first phrasing (stable for tests).

    Priority of reactions, roughly: celebrate structural completeness, warn
    about hard errors (no start, nondeterminism in a DFA), then gentler
    nudges (missing DFA move, no accept yet, epsilon hint, edge praise).
    """
    etype = event.get("type", "")
    n_states = len(aut.states)
    has_start = aut.start_state() is not None
    has_accept = bool(aut.accept_states())

    # --- Completeness beats everything: tell them they can Check. --------
    if _structurally_complete(problem, aut) and etype not in ("idle", "erase"):
        return CoachTip(
            text=_pick([
                "Looks complete — hit Check, or trace a word first.",
                "That's a full machine — Check it (or test a word).",
            ], seed),
            tone="goal",
        )

    # --- First state ever placed. ---------------------------------------
    if etype == "add_state":
        name = event.get("name")
        if n_states == 1:
            return CoachTip(
                text=_pick([
                    "Nice — your first state is the start.",
                    "Good start. First state doubles as the start state.",
                ], seed),
                tone="praise",
                focus_state=name,
            )
        # A later state exists but nobody is the start yet.
        if not has_start:
            return CoachTip(
                text="No start state yet — mark one.",
                tone="warn",
                focus_state=aut.start_state() or name,
            )
        # DFA that's now missing a move somewhere worth flagging.
        if _wants_dfa(problem):
            gap = _missing_dfa_move(aut)
            if gap:
                st, sym = gap
                return CoachTip(
                    text=f"State {st} still needs a move on '{sym}'.",
                    tone="hint",
                    focus_state=st,
                )
        # A couple of states and still no accept — ask which one wins.
        if n_states >= 2 and not has_accept:
            return CoachTip(
                text="Which state means 'accepted'? Mark it.",
                tone="hint",
            )
        return None

    # --- An edge was added. ---------------------------------------------
    if etype == "add_edge":
        # DFA with two moves on one symbol = nondeterminism.
        if _wants_dfa(problem):
            bad = _nondeterministic_state(aut)
            if bad:
                st, sym = bad
                return CoachTip(
                    text=f"Two moves on '{sym}' from {st} — fine for an NFA, not a DFA.",
                    tone="warn",
                    focus_state=st,
                )
            gap = _missing_dfa_move(aut)
            if gap:
                st, sym = gap
                return CoachTip(
                    text=f"Edge added — now give {st} a move on '{sym}'.",
                    tone="hint",
                    focus_state=st,
                )
        return CoachTip(
            text=_pick(["Edge wired.", "Nice, that's wired up."], seed),
            tone="praise",
        )

    # --- Marking start / accept. ----------------------------------------
    if etype == "mark_start":
        if _wants_dfa(problem):
            gap = _missing_dfa_move(aut)
            if gap and n_states >= 1:
                st, sym = gap
                return CoachTip(
                    text=f"Start set. {st} still needs a move on '{sym}'.",
                    tone="hint",
                    focus_state=st,
                )
        if not has_accept:
            return CoachTip(
                text="Start set — now mark where a word is accepted.",
                tone="hint",
            )
        return CoachTip(text="Start set.", tone="praise",
                        focus_state=event.get("name"))

    if etype == "mark_accept":
        if not has_start:
            return CoachTip(text="Accept set — but no start state yet.",
                            tone="warn")
        return CoachTip(
            text=_pick(["Accept marked.", "Good — that's your winning state."], seed),
            tone="praise",
            focus_state=event.get("name"),
        )

    # --- Erase: only speak if it broke something important. -------------
    if etype == "erase":
        if n_states > 0 and not has_start:
            return CoachTip(text="No start state now — mark one.", tone="warn")
        if n_states > 0 and not has_accept:
            return CoachTip(text="No accepting state left — mark one.", tone="warn")
        return None

    # --- Idle: offer the most relevant gentle nudge, else stay quiet. ---
    if etype == "idle":
        if n_states == 0:
            return CoachTip(text="Drop a state to begin.", tone="hint")
        if not has_start:
            return CoachTip(text="No start state yet — mark one.", tone="warn")
        if not has_accept and n_states >= 2:
            return CoachTip(text="Which state means 'accepted'? Mark it.", tone="hint")
        # Epsilon chapter: nudge the ε trick if they haven't tried it.
        if problem.chapter == "epsilon" and not aut.uses_epsilon():
            return CoachTip(
                text="Tip: an ε edge glues two states for free — try one.",
                tone="hint",
            )
        if _wants_dfa(problem):
            gap = _missing_dfa_move(aut)
            if gap:
                st, sym = gap
                return CoachTip(
                    text=f"{st} has no move on '{sym}' yet — a DFA needs one per symbol.",
                    tone="hint",
                    focus_state=st,
                )
        return None

    # Unknown event: say nothing.
    return None


# ---------------------------------------------------------------------- #
# 3. Solve / fail reactions
# ---------------------------------------------------------------------- #
def celebrate_tip(stars: int) -> CoachTip:
    """Return a short, upbeat reaction to a solve, scaled by `stars` (0-3)."""
    if stars >= 3:
        text = "Flawless — three stars! ⭐⭐⭐"
    elif stars == 2:
        text = "Solved, two stars. Tighten it for three."
    elif stars == 1:
        text = "Solved — one star. You've got this."
    else:
        text = "Solved! On to the next."
    return CoachTip(text=text, tone="praise")


def wrong_tip(counterexample: Optional[str]) -> CoachTip:
    """Return a short nudge after a failed check.

    If a counterexample word is known, point the player straight at it and
    tell them to follow the token-by-token trace.
    """
    if counterexample:
        ce = counterexample if counterexample else "ε"
        return CoachTip(
            text=f"Watch '{ce}' — on that word it does the wrong thing. Follow the token.",
            tone="warn",
        )
    return CoachTip(
        text="Not yet — trace a failing word to see where it goes astray.",
        tone="warn",
    )


# ---------------------------------------------------------------------- #
# 4. Step-by-step trace narration
# ---------------------------------------------------------------------- #
def _fmt_set(states: Any) -> str:
    """Format a set of state names compactly, e.g. {q0, q1} or {} (stuck)."""
    names = sorted(states)
    if not names:
        return "{} (stuck)"
    return "{" + ", ".join(names) + "}"


def trace_narration(problem: Problem,
                    aut: Automaton,
                    word: str) -> List[str]:
    """Return a terse per-step narration of running `aut` on `word`.

    Each line is tiny (e.g. "read 1 → {q1}"); the final line is the verdict
    "ACCEPTED ✓" or "REJECTED ✗", matching `aut.simulate(word)`. If the
    machine can't run (e.g. no start, or a symbol outside the alphabet) the
    list ends with a short error line and "REJECTED ✗".
    """
    sim = aut.simulate(word)
    shown = word if word else "ε"
    lines: List[str] = [f"trace '{shown}'"]

    for step in sim.steps:
        if step.symbol is None:
            # Start step or a 'stuck' note; show where we begin / end up.
            if step.index == 0:
                lines.append(f"start in {_fmt_set(step.after)}")
            elif not step.after:
                lines.append("stuck — no moves left")
        else:
            lines.append(f"read {step.symbol} → {_fmt_set(step.after)}")

    if sim.error:
        lines.append(f"⚠ {sim.error}")

    lines.append("ACCEPTED ✓" if sim.accepted else "REJECTED ✗")
    return lines
