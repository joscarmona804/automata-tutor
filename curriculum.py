"""
curriculum.py
-------------
The learning spine of Automata Tutor: an ordered list of CHAPTERS, each with a
concise teaching LESSON that is shown before the chapter's problems.

Chapters build concept-first:
    1. dfa      — what a DFA is
    2. nfa      — nondeterminism
    3. epsilon  — ε-transitions
    4. regex    — regular expressions
    5. convert  — NFA→DFA and DFA/NFA/RE equivalence

All prose is written in our own words; concepts follow Michael Sipser,
*Introduction to the Theory of Computation*, Chapter 1 (cited, not quoted).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class Chapter:
    cid: str                 # stable id, e.g. "dfa"
    title: str               # display title
    subtitle: str            # one-line hook
    sipser_ref: str          # e.g. "Sipser §1.1"
    # Lesson is a list of (heading, body) sections rendered on the lesson card.
    lesson: List[tuple] = field(default_factory=list)
    # Short, punchy "key ideas" shown as bullet chips.
    key_ideas: List[str] = field(default_factory=list)


CHAPTERS: List[Chapter] = [
    Chapter(
        cid="dfa",
        title="Chapter 1 · Deterministic Finite Automata",
        subtitle="A machine with finite memory that reads a string and says yes or no.",
        sipser_ref="Sipser §1.1",
        lesson=[
            ("What is a DFA?",
             "A deterministic finite automaton is the simplest model of a "
             "computer: a fixed set of states, a start state, and some "
             "accepting states. It reads a string one symbol at a time, "
             "following exactly one transition per symbol. If it finishes in "
             "an accepting state, the string is accepted; otherwise it is "
             "rejected."),
            ("The five pieces",
             "Formally a DFA is (Q, Σ, δ, q0, F): states Q, alphabet Σ, a "
             "transition function δ that maps (state, symbol) to one state, a "
             "start state q0, and a set of accepting states F. 'Deterministic' "
             "means δ gives exactly one next state for every (state, symbol) "
             "pair — no choices, no gaps."),
            ("How to think about states",
             "Each state is a memory of 'what matters so far'. A DFA cannot "
             "count arbitrarily, but it can remember a bounded fact: the last "
             "symbol seen, a running parity, or how much of a pattern has been "
             "matched. Design the states around that fact."),
        ],
        key_ideas=[
            "One start state",
            "Exactly one transition per symbol",
            "Accept = finish in a final state",
            "States = bounded memory",
        ],
    ),
    Chapter(
        cid="nfa",
        title="Chapter 2 · Nondeterministic Finite Automata",
        subtitle="Let the machine explore many paths at once — and accept if any path wins.",
        sipser_ref="Sipser §1.2",
        lesson=[
            ("What changes with an NFA?",
             "A nondeterministic finite automaton may have several transitions "
             "on the same symbol, or none at all. Think of it as exploring "
             "every possibility in parallel. The string is accepted if at "
             "least one of those paths ends in an accepting state."),
            ("Why bother?",
             "NFAs are often far smaller and easier to design than the "
             "equivalent DFA. 'Guess-and-check' languages — like 'the third "
             "symbol from the end is 1' — are tiny as NFAs but need many states "
             "as DFAs. The NFA guesses the right spot and the accepting path "
             "confirms it."),
            ("Same power, different style",
             "NFAs recognize exactly the same languages as DFAs — the regular "
             "languages. They are not more powerful, just more convenient. "
             "Chapter 5 shows how to convert one into the other."),
        ],
        key_ideas=[
            "Many moves on one symbol — allowed",
            "Zero moves — allowed (path dies)",
            "Accept if ANY path accepts",
            "Smaller than the equivalent DFA",
        ],
    ),
    Chapter(
        cid="epsilon",
        title="Chapter 3 · ε-Transitions",
        subtitle="Move between states for free, without reading any input.",
        sipser_ref="Sipser §1.2",
        lesson=[
            ("The empty move",
             "An ε-transition lets an NFA jump from one state to another "
             "without consuming a symbol. It is a 'free' move. This makes it "
             "effortless to glue machines together — the core trick behind "
             "turning regular expressions into automata."),
            ("ε-closure",
             "Before and after reading each symbol, you take every ε-move "
             "available. The ε-closure of a set of states is all states "
             "reachable from them using only ε-arrows. Simulation tracks the "
             "ε-closure of the current states at every step."),
            ("Still just regular",
             "Adding ε-transitions does not add power: an NFA with ε-moves can "
             "always be rewritten without them, and still recognizes a regular "
             "language. They are a convenience for construction."),
        ],
        key_ideas=[
            "ε = move without reading input",
            "ε-closure = free reachable states",
            "Great for gluing machines",
            "No extra power — still regular",
        ],
    ),
    Chapter(
        cid="regex",
        title="Chapter 4 · Regular Expressions",
        subtitle="Describe a language directly with union, concatenation, and star.",
        sipser_ref="Sipser §1.3",
        lesson=[
            ("Three operations",
             "Regular expressions build languages from three operators: union "
             "'a|b' (either), concatenation 'ab' (one then the other), and "
             "Kleene star 'a*' (zero or more repeats). With parentheses for "
             "grouping, that is the whole language."),
            ("Reading and writing them",
             "'(0|1)*' means any binary string. Concatenating a literal pins "
             "down a pattern: '(0|1)*01' is 'anything, ending in 01'. Star "
             "wraps a block you want repeated. Precedence is star, then "
             "concatenation, then union — like exponent, multiply, add."),
            ("Equivalence",
             "A language can be written as a regular expression exactly when "
             "it is regular — the same class DFAs and NFAs recognize. "
             "Expressions, DFAs, and NFAs are three views of one idea."),
        ],
        key_ideas=[
            "| = union (choice)",
            "concatenation = sequence",
            "* = zero or more",
            "Describes exactly the regular languages",
        ],
    ),
    Chapter(
        cid="convert",
        title="Chapter 5 · Conversions & Equivalence",
        subtitle="NFA → DFA by the subset construction, and the big equivalence picture.",
        sipser_ref="Sipser §1.2–§1.3",
        lesson=[
            ("Subset construction",
             "To turn an NFA into a DFA, make each DFA state a SET of NFA "
             "states — exactly the set the NFA could currently be in. The DFA "
             "start state is the ε-closure of the NFA start. On a symbol, take "
             "every NFA move from the whole set, then its ε-closure. A DFA "
             "state accepts if its set contains any NFA accepting state."),
            ("Why it works",
             "The set of 'possible current states' is itself a finite, "
             "well-defined thing, and it updates deterministically. There are "
             "only finitely many subsets, so the DFA is finite — at most 2^n "
             "states for n NFA states, though usually far fewer are reachable."),
            ("The equivalence triangle",
             "DFAs, NFAs, and regular expressions all describe the same "
             "languages. You can convert any one into any other: NFA→DFA by "
             "subset construction, regex→NFA by gluing with ε-moves, and "
             "automaton→regex by state elimination. Three notations, one class "
             "of languages."),
        ],
        key_ideas=[
            "DFA state = SET of NFA states",
            "Start = ε-closure of NFA start",
            "Accept if the set hits a final state",
            "DFA ≡ NFA ≡ regex",
        ],
    ),
]

CHAPTER_INDEX: Dict[str, int] = {c.cid: i for i, c in enumerate(CHAPTERS)}


def get_chapter(cid: str) -> Chapter:
    for c in CHAPTERS:
        if c.cid == cid:
            return c
    return CHAPTERS[0]


def chapter_order(cid: str) -> int:
    """Position of a chapter in the campaign (0-based); large if unknown."""
    return CHAPTER_INDEX.get(cid, len(CHAPTERS))
