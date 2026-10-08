"""
automaton.py
------------
Core data model for finite automata (DFA / NFA) and a small engine to
simulate them step-by-step. Pure Python, no external dependencies.

The classes here are deliberately simple and well-documented so they can
double as a teaching reference for a CS3110-style automata course.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, FrozenSet, Optional

EPSILON = "ε"  # label used for epsilon (empty-string) transitions


@dataclass
class State:
    """A single state in an automaton.

    Attributes:
        name:       Human-readable label, e.g. "q0".
        x, y:       Canvas coordinates (used by the GUI, ignored by logic).
        is_start:   True if this is the (unique) start state.
        is_accept:  True if this is an accepting / final state.
    """
    name: str
    x: float = 0.0
    y: float = 0.0
    is_start: bool = False
    is_accept: bool = False


@dataclass
class Automaton:
    """A finite automaton that can represent either a DFA or an NFA.

    Transitions are stored as a mapping:
        (source_state_name, symbol) -> set of destination state names

    Using a set of destinations lets the same structure describe both
    DFAs (every set has at most one element and ε is unused) and NFAs
    (sets may have 0, 1, or many elements and ε transitions are allowed).
    """
    states: Dict[str, State] = field(default_factory=dict)
    alphabet: Set[str] = field(default_factory=set)
    transitions: Dict[Tuple[str, str], Set[str]] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # Construction helpers
    # ------------------------------------------------------------------ #
    def add_state(self, name: str, x: float = 0.0, y: float = 0.0,
                  is_start: bool = False, is_accept: bool = False) -> State:
        st = State(name=name, x=x, y=y, is_start=is_start, is_accept=is_accept)
        if is_start:
            # Enforce a single start state.
            for other in self.states.values():
                other.is_start = False
        self.states[name] = st
        return st

    def remove_state(self, name: str) -> None:
        self.states.pop(name, None)
        # Drop any transition that touches the removed state.
        for key in list(self.transitions.keys()):
            src, _sym = key
            if src == name:
                del self.transitions[key]
                continue
            self.transitions[key].discard(name)
            if not self.transitions[key]:
                del self.transitions[key]

    def add_transition(self, src: str, symbol: str, dst: str) -> None:
        if symbol != EPSILON:
            self.alphabet.add(symbol)
        self.transitions.setdefault((src, symbol), set()).add(dst)

    def remove_transition(self, src: str, symbol: str, dst: str) -> None:
        key = (src, symbol)
        if key in self.transitions:
            self.transitions[key].discard(dst)
            if not self.transitions[key]:
                del self.transitions[key]

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #
    def start_state(self) -> Optional[str]:
        for name, st in self.states.items():
            if st.is_start:
                return name
        return None

    def accept_states(self) -> Set[str]:
        return {n for n, s in self.states.items() if s.is_accept}

    def moves(self, src: str, symbol: str) -> Set[str]:
        return set(self.transitions.get((src, symbol), set()))

    def uses_epsilon(self) -> bool:
        return any(sym == EPSILON for (_s, sym) in self.transitions)

    def is_deterministic(self) -> Tuple[bool, List[str]]:
        """Return (is_dfa, reasons). A DFA must:
          * have exactly one start state,
          * have no epsilon transitions, and
          * for every state and every alphabet symbol, have exactly
            one defined transition.
        """
        reasons: List[str] = []

        starts = [n for n, s in self.states.items() if s.is_start]
        if len(starts) != 1:
            reasons.append(
                f"A DFA needs exactly one start state (found {len(starts)})."
            )

        if self.uses_epsilon():
            reasons.append("A DFA cannot use ε (epsilon) transitions.")

        for name in self.states:
            for sym in sorted(self.alphabet):
                dests = self.moves(name, sym)
                if len(dests) == 0:
                    reasons.append(
                        f"State {name} has no transition on '{sym}' "
                        f"(DFAs must be total)."
                    )
                elif len(dests) > 1:
                    reasons.append(
                        f"State {name} has {len(dests)} transitions on "
                        f"'{sym}' (DFAs allow at most one)."
                    )

        return (len(reasons) == 0, reasons)

    # ------------------------------------------------------------------ #
    # Epsilon-closure + simulation
    # ------------------------------------------------------------------ #
    def epsilon_closure(self, states: Set[str]) -> Set[str]:
        """All states reachable from `states` using only ε transitions."""
        stack = list(states)
        closure: Set[str] = set(states)
        while stack:
            s = stack.pop()
            for nxt in self.moves(s, EPSILON):
                if nxt not in closure:
                    closure.add(nxt)
                    stack.append(nxt)
        return closure

    def simulate(self, word: str) -> "Simulation":
        """Run the automaton on `word` and record every step.

        Works for both DFAs and NFAs. For NFAs we track the *set* of
        currently-active states (subset simulation) including ε-closures.
        """
        steps: List[SimStep] = []
        start = self.start_state()
        if start is None:
            return Simulation(word=word, steps=[], accepted=False,
                              error="No start state is defined.")

        current = self.epsilon_closure({start})
        steps.append(SimStep(
            index=0,
            symbol=None,
            before=set(current),
            after=set(current),
            note=f"Start in {_fmt(current)} (after ε-closure of start state)."
        ))

        for i, ch in enumerate(word):
            if ch not in self.alphabet:
                return Simulation(
                    word=word, steps=steps, accepted=False,
                    error=f"Symbol '{ch}' is not in the alphabet "
                          f"{{{', '.join(sorted(self.alphabet))}}}."
                )
            before = set(current)
            moved: Set[str] = set()
            for s in current:
                moved |= self.moves(s, ch)
            after = self.epsilon_closure(moved)
            steps.append(SimStep(
                index=i + 1,
                symbol=ch,
                before=before,
                after=set(after),
                note=_describe_move(before, ch, moved, after)
            ))
            current = after
            if not current:
                steps.append(SimStep(
                    index=i + 1, symbol=None,
                    before=set(), after=set(),
                    note="No active states remain — the automaton is stuck, "
                         "so the word is rejected."
                ))
                return Simulation(word=word, steps=steps, accepted=False)

        accepting = current & self.accept_states()
        accepted = bool(accepting)
        return Simulation(word=word, steps=steps, accepted=accepted)


# ---------------------------------------------------------------------- #
# Simulation result containers
# ---------------------------------------------------------------------- #
@dataclass
class SimStep:
    index: int
    symbol: Optional[str]
    before: Set[str]
    after: Set[str]
    note: str


@dataclass
class Simulation:
    word: str
    steps: List[SimStep]
    accepted: bool
    error: Optional[str] = None


# ---------------------------------------------------------------------- #
# Small formatting helpers used in explanation text
# ---------------------------------------------------------------------- #
def _fmt(states: Set[str]) -> str:
    if not states:
        return "{} (empty)"
    return "{" + ", ".join(sorted(states)) + "}"


def _describe_move(before: Set[str], symbol: str,
                   moved: Set[str], after: Set[str]) -> str:
    base = f"Read '{symbol}'. From {_fmt(before)} we move to {_fmt(moved)}."
    if after != moved:
        base += f" After taking ε-transitions this becomes {_fmt(after)}."
    return base
