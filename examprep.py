"""
examprep.py
-----------
Pure-logic engine for an EXAM-PREP / practice mode in Automata Tutor.

This module has NO GUI dependencies (no tkinter). Everything here is
gradeable on paper, which makes it the right companion for a written exam
covering Sipser, *Introduction to the Theory of Computation*, Chapter 1
(DFAs, NFAs, ε-transitions, regular expressions, and NFA→DFA conversion).

It adds two things on top of the build-an-automaton PROBLEMS in ``quiz.py``:

1.  A hand-written bank of conceptual multiple-choice / true-false
    questions (:data:`CONCEPT_QUESTIONS`) spanning all five chapters.
2.  Programmatically generated "membership" questions built from the real
    ``quiz.PROBLEMS`` language predicates (see
    :func:`generate_membership_questions`).

Those feed an :class:`ExamSession` that assembles a balanced, optionally
timed mixed quiz, grades answers, and reports per-topic performance so a
student can see weak areas. :func:`recommended_focus` turns that into a
short "review these chapters" list.

Design notes
------------
*   A :class:`Question` is a single uniform record for three formats:
    ``"mcq"``, ``"membership"`` (really an MCQ with ACCEPT/REJECT options),
    and ``"true_false"``. The correct choice is always an index into
    :attr:`Question.options`; the convenience property
    :attr:`Question.boolean` interprets a true/false question's answer.
*   Topics are chapter ids from :mod:`curriculum`:
    ``"dfa"``, ``"nfa"``, ``"epsilon"``, ``"regex"``, ``"convert"``.
*   The session clock is injectable (``clock=time.monotonic`` by default)
    so timing is testable and never blocks.

All explanations are written in our own words; Sipser sections are cited,
not quoted. Every hand-written answer has been checked by the throwaway
correctness gate described in the module's development notes.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import quiz
from quiz import Problem

# Chapter ids used as "topics". Kept as a plain tuple so this module does
# not need to import curriculum at runtime, but these match curriculum.CHAPTERS.
TOPICS: Tuple[str, ...] = ("dfa", "nfa", "epsilon", "regex", "convert")

# Accept / reject are the fixed options for membership questions. Index 0
# means ACCEPT, index 1 means REJECT.
_MEMBERSHIP_OPTIONS: List[str] = ["ACCEPT", "REJECT"]
# True / false options for true_false questions. Index 0 means True.
_TF_OPTIONS: List[str] = ["True", "False"]


# ---------------------------------------------------------------------- #
# The Question record
# ---------------------------------------------------------------------- #
@dataclass
class Question:
    """A single gradeable exam-prep question.

    One record covers three formats, distinguished by :attr:`kind`:

    *   ``"mcq"`` — a conceptual multiple-choice question with 3+ options.
    *   ``"true_false"`` — a statement; options are ``["True", "False"]``
        and :attr:`answer_index` is 0 for a true statement, 1 for false.
    *   ``"membership"`` — a described language plus a specific string; the
        options are ``["ACCEPT", "REJECT"]`` and :attr:`answer_index` says
        which is correct (computed from a live membership predicate).

    Attributes:
        qid:          Stable, unique id string for this question.
        kind:         One of ``"mcq"``, ``"true_false"``, ``"membership"``.
        topic:        Chapter id (see :data:`TOPICS`).
        stem:         The question text shown to the student.
        options:      The selectable answers (indexable choices).
        answer_index: Index into :attr:`options` of the correct answer.
        explanation:  A concise (1-3 sentence) rationale in our own words.
        difficulty:   1 (easiest) .. 5 (hardest); used only for display/mix.
        language:     For ``"membership"``, the problem title; else None.
        word:         For ``"membership"``, the tested string; else None.
    """

    qid: str
    kind: str
    topic: str
    stem: str
    options: List[str]
    answer_index: int
    explanation: str
    difficulty: int = 1
    language: Optional[str] = None
    word: Optional[str] = None

    def __post_init__(self) -> None:
        if self.kind not in ("mcq", "true_false", "membership"):
            raise ValueError(f"Unknown question kind: {self.kind!r}")
        if not self.options:
            raise ValueError(f"Question {self.qid} has no options.")
        if not 0 <= self.answer_index < len(self.options):
            raise ValueError(
                f"Question {self.qid}: answer_index {self.answer_index} is "
                f"out of range for {len(self.options)} options."
            )
        if self.topic not in TOPICS:
            raise ValueError(
                f"Question {self.qid}: topic {self.topic!r} is not one of "
                f"{TOPICS}."
            )

    # -- convenience accessors ------------------------------------------
    @property
    def boolean(self) -> bool:
        """For a ``"true_false"`` question, the correct boolean answer.

        True statements store ``answer_index == 0`` (the "True" option).

        Raises:
            ValueError: if called on a question that is not true/false.
        """
        if self.kind != "true_false":
            raise ValueError(
                f"Question {self.qid} is {self.kind!r}, not 'true_false'."
            )
        return self.answer_index == 0

    @property
    def correct_option(self) -> str:
        """The text of the correct option."""
        return self.options[self.answer_index]

    def is_correct(self, choice: object) -> bool:
        """Grade a student's ``choice`` against this question.

        Accepts several natural answer shapes so callers (and GUIs) can be
        forgiving:

        *   an ``int`` option index,
        *   a ``bool`` (only meaningful for ``"true_false"``),
        *   a ``str`` matching an option (case-insensitively), such as
            ``"ACCEPT"``, ``"True"``, or the full option text.

        Returns:
            True iff ``choice`` identifies the correct option.
        """
        idx = self._normalize_choice(choice)
        return idx == self.answer_index

    def _normalize_choice(self, choice: object) -> Optional[int]:
        """Map a flexible ``choice`` onto an option index (or None)."""
        if isinstance(choice, bool):
            # Must come before int: bool is a subclass of int in Python.
            return 0 if choice else 1
        if isinstance(choice, int):
            return choice
        if isinstance(choice, str):
            text = choice.strip().lower()
            for i, opt in enumerate(self.options):
                if opt.strip().lower() == text:
                    return i
            # Accept common synonyms for boolean / membership answers.
            synonyms: Dict[str, int] = {
                "true": 0, "t": 0, "yes": 0, "y": 0, "accept": 0, "a": 0,
                "false": 1, "f": 1, "no": 1, "n": 1, "reject": 1, "r": 1,
            }
            if text in synonyms and len(self.options) == 2:
                return synonyms[text]
        return None


# ---------------------------------------------------------------------- #
# Hand-written conceptual question bank
# ---------------------------------------------------------------------- #
def _mcq(qid: str, topic: str, stem: str, options: List[str],
         answer_index: int, explanation: str, difficulty: int = 2) -> Question:
    """Build a conceptual multiple-choice :class:`Question`."""
    return Question(
        qid=qid, kind="mcq", topic=topic, stem=stem, options=list(options),
        answer_index=answer_index, explanation=explanation,
        difficulty=difficulty,
    )


def _tf(qid: str, topic: str, statement: str, is_true: bool,
        explanation: str, difficulty: int = 2) -> Question:
    """Build a true/false :class:`Question` (True option is index 0)."""
    return Question(
        qid=qid, kind="true_false", topic=topic, stem=statement,
        options=list(_TF_OPTIONS), answer_index=0 if is_true else 1,
        explanation=explanation, difficulty=difficulty,
    )


# NOTE: every answer below was verified by the correctness gate. All claims
# are strictly within Sipser Chapter 1 (regular languages); no pumping lemma
# or anything beyond Ch.1 appears.
CONCEPT_QUESTIONS: List[Question] = [
    # ===== dfa ========================================================= #
    _mcq(
        "c_dfa_trans_count", "dfa",
        "In a DFA, how many transitions leave each state for a given "
        "alphabet symbol?",
        ["Zero or one", "Exactly one", "At least one", "Any number"],
        1,
        "A DFA's transition function is total and single-valued: every "
        "(state, symbol) pair maps to exactly one next state (Sipser §1.1).",
        difficulty=1,
    ),
    _mcq(
        "c_dfa_tuple", "dfa",
        "A DFA is formally a 5-tuple. Which collection is it?",
        ["(Q, Σ, δ, q0, F)", "(Q, Σ, δ, F)", "(Q, δ, q0, F)",
         "(states, stack, δ, q0, F)"],
        0,
        "A DFA is (Q, Σ, δ, q0, F): states, alphabet, transition function, "
        "start state, and accept states (Sipser §1.1). There is no stack — "
        "that would be a pushdown automaton.",
        difficulty=1,
    ),
    _mcq(
        "c_dfa_start_count", "dfa",
        "How many start states does a DFA have?",
        ["Zero", "Exactly one", "One per alphabet symbol",
         "Any number"],
        1,
        "A DFA has exactly one start state q0 (Sipser §1.1). Multiple start "
        "states would introduce the very nondeterminism a DFA forbids.",
        difficulty=1,
    ),
    _mcq(
        "c_dfa_accept_rule", "dfa",
        "A DFA accepts an input string exactly when:",
        ["it visits an accept state at some point",
         "it ends in an accept state after reading all input",
         "every state it visits is accepting",
         "it never gets stuck"],
        1,
        "Acceptance is decided only at the end: the DFA accepts iff the "
        "state reached after consuming the whole string is in F (Sipser §1.1).",
        difficulty=2,
    ),
    _mcq(
        "c_dfa_memory", "dfa",
        "What kind of memory does a finite automaton have?",
        ["Unbounded, like a counter", "A bounded amount, fixed by its states",
         "A stack of unbounded depth", "Random-access memory"],
        1,
        "A finite automaton's only memory is its current state, so it can "
        "remember just a bounded, fixed amount of information (Sipser §1.1).",
        difficulty=2,
    ),
    _tf(
        "c_dfa_total", "dfa",
        "In a DFA every state must have a defined transition for every "
        "symbol of the alphabet.",
        True,
        "A DFA's transition function is total: each state defines a move on "
        "every alphabet symbol, which is why a 'dead' sink state is often "
        "added (Sipser §1.1).",
        difficulty=2,
    ),
    _tf(
        "c_dfa_empty_accept", "dfa",
        "A DFA accepts the empty string ε if and only if its start state is "
        "an accept state.",
        True,
        "With no symbols to read, the machine stays in q0; it accepts ε "
        "exactly when q0 ∈ F (Sipser §1.1).",
        difficulty=2,
    ),

    # ===== nfa ========================================================= #
    _mcq(
        "c_nfa_accept_rule", "nfa",
        "An NFA accepts a string when:",
        ["every computation path ends in an accept state",
         "at least one computation path ends in an accept state",
         "the majority of paths accept",
         "the first path tried accepts"],
        1,
        "Nondeterministic acceptance is existential: the NFA accepts iff "
        "SOME path through its choices ends in an accept state (Sipser §1.2).",
        difficulty=2,
    ),
    _mcq(
        "c_nfa_trans_count", "nfa",
        "For a given state and input symbol, an NFA may have how many "
        "transitions?",
        ["Exactly one", "Exactly two", "Zero, one, or many",
         "At most one"],
        2,
        "An NFA's transition function maps a (state, symbol) pair to a SET "
        "of states, which may be empty, a singleton, or many (Sipser §1.2).",
        difficulty=1,
    ),
    _mcq(
        "c_nfa_power", "nfa",
        "Compared with DFAs, which languages can NFAs recognize?",
        ["A strictly larger class", "Exactly the same class (regular)",
         "Only finite languages", "A strictly smaller class"],
        1,
        "NFAs and DFAs recognize exactly the same class — the regular "
        "languages. Nondeterminism adds convenience, not power (Sipser §1.2).",
        difficulty=2,
    ),
    _mcq(
        "c_nfa_dead_path", "nfa",
        "In an NFA, if the current symbol has no outgoing transition from "
        "the current state, that computation path:",
        ["rejects the whole input immediately",
         "dies, but other paths may still accept",
         "loops back to the start",
         "takes an ε-move automatically"],
        1,
        "A path with no legal move simply dies; the NFA still accepts if any "
        "OTHER surviving path ends in an accept state (Sipser §1.2).",
        difficulty=2,
    ),
    _mcq(
        "c_nfa_guess", "nfa",
        "Why is an NFA for 'the third symbol from the end is 1' much smaller "
        "than the equivalent DFA?",
        ["It uses a stack to remember position",
         "It can nondeterministically guess which symbol is third from last",
         "It reads the string backwards",
         "It needs no accept state"],
        1,
        "The NFA guesses the key position and uses a short chain to confirm "
        "it; a DFA must instead remember the last three symbols in its "
        "states (Sipser §1.2).",
        difficulty=3,
    ),
    _tf(
        "c_nfa_every_dfa", "nfa",
        "Every DFA is also, trivially, an NFA.",
        True,
        "A DFA satisfies the NFA definition — each (state, symbol) just maps "
        "to a one-element set and no ε-moves are used (Sipser §1.2).",
        difficulty=1,
    ),

    # ===== epsilon ===================================================== #
    _mcq(
        "c_eps_meaning", "epsilon",
        "What does an ε-transition let an automaton do?",
        ["Read two symbols at once",
         "Change state without consuming an input symbol",
         "Delete the last symbol read",
         "Reset to the start state"],
        1,
        "An ε-transition is a 'free' move: the machine changes state without "
        "reading any input symbol (Sipser §1.2).",
        difficulty=1,
    ),
    _mcq(
        "c_eps_closure", "epsilon",
        "The ε-closure of a set S of states is:",
        ["every state reachable from S using only ε-transitions (S included)",
         "every accept state reachable from S",
         "the set of states that can reach S on input",
         "the states reachable from S on exactly one symbol"],
        0,
        "The ε-closure of S is all states reachable from members of S by "
        "following ε-arrows (zero or more), and it always contains S itself "
        "(Sipser §1.2).",
        difficulty=2,
    ),
    _mcq(
        "c_eps_power", "epsilon",
        "Allowing ε-transitions in an NFA:",
        ["adds the power to recognize some non-regular languages",
         "does not change the class of languages recognized",
         "makes the machine deterministic",
         "requires an infinite number of states"],
        1,
        "ε-moves are a construction convenience; any ε-NFA can be rewritten "
        "without them and still recognizes a regular language (Sipser §1.2).",
        difficulty=2,
    ),
    _mcq(
        "c_eps_sim_step", "epsilon",
        "When simulating an ε-NFA, after moving on an input symbol you must:",
        ["take the ε-closure of the resulting set of states",
         "pick a single next state arbitrarily",
         "remove all accept states",
         "ignore ε-edges until the end"],
        0,
        "Each step reads a symbol and then takes the ε-closure of the states "
        "reached, so all free moves are accounted for before the next symbol "
        "(Sipser §1.2).",
        difficulty=3,
    ),
    _tf(
        "c_eps_in_closure", "epsilon",
        "A state is always a member of its own ε-closure.",
        True,
        "The ε-closure includes the starting states themselves (reachable by "
        "zero ε-moves) plus anything reachable via ε-arrows (Sipser §1.2).",
        difficulty=1,
    ),
    _tf(
        "c_eps_glue", "epsilon",
        "ε-transitions make it easy to glue smaller machines together, which "
        "is central to converting regular expressions into automata.",
        True,
        "Thompson's construction uses ε-edges to wire up union, "
        "concatenation, and star from small fragments (Sipser §1.2–§1.3).",
        difficulty=2,
    ),

    # ===== regex ======================================================= #
    _mcq(
        "c_re_operators", "regex",
        "The three operations that build regular expressions are:",
        ["union, concatenation, and Kleene star",
         "union, intersection, and complement",
         "concatenation, reversal, and star",
         "and, or, not"],
        0,
        "Regular expressions are built from union (|), concatenation, and "
        "the Kleene star (*), with parentheses for grouping (Sipser §1.3).",
        difficulty=1,
    ),
    _mcq(
        "c_re_precedence", "regex",
        "From highest to lowest, the precedence of regex operators is:",
        ["union, then concatenation, then star",
         "star, then concatenation, then union",
         "concatenation, then star, then union",
         "they all have equal precedence"],
        1,
        "Star binds tightest, then concatenation, then union — analogous to "
        "exponent, multiply, add. So ab*|c parses as (a(b*))|c (Sipser §1.3).",
        difficulty=3,
    ),
    _mcq(
        "c_re_star_meaning", "regex",
        "The expression a* denotes:",
        ["exactly one a", "one or more a's", "zero or more a's",
         "any string containing an a"],
        2,
        "The Kleene star means zero or more repetitions, so a* includes the "
        "empty string ε as well as a, aa, aaa, … (Sipser §1.3).",
        difficulty=1,
    ),
    _mcq(
        "c_re_binary_all", "regex",
        "Over the alphabet {0,1}, which regular expression denotes ALL "
        "binary strings (including the empty string)?",
        ["(0|1)", "(0|1)*", "01*", "0*1*"],
        1,
        "(0|1)* is zero or more of 'either 0 or 1', i.e. every possible "
        "binary string, ε included (Sipser §1.3).",
        difficulty=1,
    ),
    _mcq(
        "c_re_eps_vs_empty", "regex",
        "What is the difference between the regular expressions ε and ∅?",
        ["They are the same",
         "ε denotes the language {ε}; ∅ denotes the empty language {}",
         "ε denotes {} and ∅ denotes {ε}",
         "ε matches any one symbol; ∅ matches none"],
        1,
        "ε denotes the one-string language {ε}, while ∅ denotes the language "
        "with no strings at all — a crucial distinction (Sipser §1.3).",
        difficulty=2,
    ),
    _mcq(
        "c_re_class", "regex",
        "A language can be described by a regular expression exactly when:",
        ["it is finite", "it is regular",
         "it is context-free but not regular", "it contains the empty string"],
        1,
        "Regular expressions describe precisely the regular languages — the "
        "same class recognized by DFAs and NFAs (Sipser §1.3).",
        difficulty=2,
    ),
    _tf(
        "c_re_concat_order", "regex",
        "In the regular expression ab, the a must be matched before the b.",
        True,
        "Concatenation is ordered: ab matches an a immediately followed by a "
        "b, not the other way around (Sipser §1.3).",
        difficulty=1,
    ),
    _tf(
        "c_re_star_empty", "regex",
        "For any regular expression R, the language of R* always contains "
        "the empty string.",
        True,
        "Zero repetitions is allowed, so ε ∈ L(R*) for every R — even when "
        "R itself cannot match ε (Sipser §1.3).",
        difficulty=2,
    ),

    # ===== convert ===================================================== #
    _mcq(
        "c_conv_state_meaning", "convert",
        "In the subset construction (NFA→DFA), each DFA state corresponds "
        "to:",
        ["a single NFA state", "a set of NFA states",
         "an input symbol", "an accept state of the NFA"],
        1,
        "Each DFA state is a SET of NFA states — exactly the collection the "
        "NFA could currently be in (Sipser §1.2).",
        difficulty=2,
    ),
    _mcq(
        "c_conv_start", "convert",
        "In the subset construction, the DFA's start state is:",
        ["the NFA's start state alone",
         "the ε-closure of the NFA's start state",
         "the set of all NFA states",
         "the NFA's accept states"],
        1,
        "The DFA starts in the ε-closure of the NFA start state, so all free "
        "moves available before reading input are included (Sipser §1.2).",
        difficulty=3,
    ),
    _mcq(
        "c_conv_accept", "convert",
        "A subset-construction DFA state (a set of NFA states) is accepting "
        "when:",
        ["all of its NFA states are accepting",
         "it contains at least one NFA accept state",
         "it is the start set",
         "it is empty"],
        1,
        "A DFA state accepts iff its set contains any NFA accept state — "
        "matching the NFA's 'some path accepts' rule (Sipser §1.2).",
        difficulty=2,
    ),
    _mcq(
        "c_conv_blowup", "convert",
        "An NFA with n states can convert, in the worst case, to a DFA with "
        "about how many states?",
        ["n", "2n", "n²", "2^n"],
        3,
        "Because DFA states are subsets of the n NFA states, there are up to "
        "2^n of them (usually far fewer are reachable) (Sipser §1.2).",
        difficulty=3,
    ),
    _mcq(
        "c_conv_dead_set", "convert",
        "During the subset construction, reaching the empty set {} as a DFA "
        "state means:",
        ["an error in the construction",
         "a non-accepting dead/trap state",
         "the start state", "an accepting state"],
        1,
        "The empty subset is a legitimate dead state: no NFA path survives, "
        "so it rejects and loops to itself on every symbol (Sipser §1.2).",
        difficulty=3,
    ),
    _mcq(
        "c_conv_equivalence", "convert",
        "Which statement about DFAs, NFAs, and regular expressions is "
        "correct?",
        ["They each describe a different class of languages",
         "They all describe exactly the regular languages",
         "Regular expressions are strictly weaker than DFAs",
         "NFAs are strictly stronger than regular expressions"],
        1,
        "DFAs, NFAs, and regular expressions are three equivalent notations "
        "for one class: the regular languages (Sipser §1.2–§1.3).",
        difficulty=2,
    ),
    _tf(
        "c_conv_always_possible", "convert",
        "Every NFA can be converted into a DFA that recognizes the same "
        "language.",
        True,
        "The subset construction always yields an equivalent DFA, proving "
        "NFAs are no more powerful than DFAs (Sipser §1.2).",
        difficulty=1,
    ),
    _tf(
        "c_conv_re_to_nfa", "convert",
        "Any regular expression can be converted into an equivalent NFA by "
        "gluing fragments with ε-transitions.",
        True,
        "Thompson's construction builds an NFA for each operator and wires "
        "them with ε-edges, giving an NFA for the whole expression "
        "(Sipser §1.3).",
        difficulty=2,
    ),
]


def concept_questions(topic: Optional[str] = None) -> List[Question]:
    """Return the hand-written conceptual questions, optionally filtered.

    Args:
        topic: If given, keep only questions whose :attr:`Question.topic`
            equals this chapter id.

    Returns:
        A new list (safe to mutate) of :class:`Question` objects.
    """
    if topic is None:
        return list(CONCEPT_QUESTIONS)
    return [q for q in CONCEPT_QUESTIONS if q.topic == topic]


def concept_counts_by_topic() -> Dict[str, int]:
    """Count hand-written conceptual questions per topic (chapter id)."""
    counts: Dict[str, int] = {t: 0 for t in TOPICS}
    for q in CONCEPT_QUESTIONS:
        counts[q.topic] = counts.get(q.topic, 0) + 1
    return counts


# ---------------------------------------------------------------------- #
# Programmatic membership questions
# ---------------------------------------------------------------------- #
def _candidate_words(problem: Problem, max_len: int = 5) -> List[str]:
    """Collect a varied pool of test strings for a problem.

    Combines the problem's own hand-picked examples with every word up to
    ``max_len`` over its alphabet, de-duplicated while preserving order.
    """
    pool: List[str] = []
    seen: set = set()

    def _add(w: str) -> None:
        if w not in seen:
            seen.add(w)
            pool.append(w)

    for w in list(problem.example_accept) + list(problem.example_reject):
        _add(w)
    for w in quiz.all_words(list(problem.alphabet), max_len):
        _add(w)
    return pool


def _membership_question(problem: Problem, word: str, qid: str) -> Question:
    """Build one ACCEPT/REJECT membership question for ``problem``/``word``."""
    accepted = bool(problem.membership(word))
    answer_index = 0 if accepted else 1  # 0 == ACCEPT, 1 == REJECT
    shown = word if word != "" else "ε (the empty string)"
    verdict = "ACCEPTS" if accepted else "REJECTS"
    return Question(
        qid=qid,
        kind="membership",
        topic=problem.chapter,
        stem=(
            f"Language \"{problem.title}\": {problem.prompt} "
            f"Should the string \"{shown}\" be ACCEPTED or REJECTED?"
        ),
        options=list(_MEMBERSHIP_OPTIONS),
        answer_index=answer_index,
        explanation=(
            f"The language \"{problem.title}\" {verdict} \"{shown}\" because "
            f"it {'satisfies' if accepted else 'violates'} the stated "
            f"condition."
        ),
        difficulty=problem.difficulty,
        language=problem.title,
        word=word,
    )


def generate_membership_questions(
    n: int,
    chapters: Optional[Sequence[str]] = None,
    seed: Optional[int] = None,
) -> List[Question]:
    """Generate ``n`` membership questions from :data:`quiz.PROBLEMS`.

    Each question picks a problem (optionally restricted to ``chapters``),
    picks one of its candidate strings, and sets the correct answer from the
    problem's live ``membership`` predicate. The chosen (problem, word) pairs
    are unique, and the generator balances accepted vs. rejected strings so a
    student sees a mix of both verdicts.

    Args:
        n: Number of questions to produce (clamped to the number of
            distinct (problem, word) pairs available).
        chapters: Optional iterable of chapter ids to restrict the source
            problems. Unknown ids simply match nothing.
        seed: Optional RNG seed for reproducible selection.

    Returns:
        A list of up to ``n`` :class:`Question` objects of kind
        ``"membership"``.
    """
    rng = random.Random(seed)

    allowed = set(chapters) if chapters is not None else None
    problems = [
        p for p in quiz.PROBLEMS
        if allowed is None or p.chapter in allowed
    ]
    if not problems or n <= 0:
        return []

    # Build the full pool of (problem, word) pairs, tagged by verdict so we
    # can balance ACCEPT vs REJECT.
    accept_pool: List[Tuple[Problem, str]] = []
    reject_pool: List[Tuple[Problem, str]] = []
    for p in problems:
        for w in _candidate_words(p):
            if p.membership(w):
                accept_pool.append((p, w))
            else:
                reject_pool.append((p, w))

    rng.shuffle(accept_pool)
    rng.shuffle(reject_pool)

    # Interleave accepted and rejected pairs for balance, falling back to
    # whichever pool still has entries.
    chosen: List[Tuple[Problem, str]] = []
    ai = ri = 0
    take_accept = True
    while len(chosen) < n and (ai < len(accept_pool) or ri < len(reject_pool)):
        if take_accept and ai < len(accept_pool):
            chosen.append(accept_pool[ai])
            ai += 1
        elif not take_accept and ri < len(reject_pool):
            chosen.append(reject_pool[ri])
            ri += 1
        elif ai < len(accept_pool):
            chosen.append(accept_pool[ai])
            ai += 1
        elif ri < len(reject_pool):
            chosen.append(reject_pool[ri])
            ri += 1
        take_accept = not take_accept

    questions: List[Question] = []
    for i, (p, w) in enumerate(chosen):
        qid = f"mem_{p.key}_{i}_{len(w)}"
        questions.append(_membership_question(p, w, qid))
    return questions


# ---------------------------------------------------------------------- #
# Exam session
# ---------------------------------------------------------------------- #
@dataclass
class AnswerRecord:
    """One recorded answer within an :class:`ExamSession`.

    Attributes:
        question:    The :class:`Question` that was answered.
        given:       The raw choice the student submitted.
        correct:     Whether :attr:`given` was the right answer.
    """
    question: Question
    given: object
    correct: bool


def build_mixed_quiz(
    total: int,
    topics: Optional[Sequence[str]] = None,
    seed: Optional[int] = None,
    membership_ratio: float = 0.4,
) -> List[Question]:
    """Assemble a balanced mixed quiz of ``total`` questions.

    Draws conceptual questions and freshly generated membership questions,
    balanced across the requested ``topics`` (default: all of
    :data:`TOPICS`). The pool is shuffled deterministically when ``seed`` is
    given.

    Args:
        total: Desired number of questions (clamped to what is available).
        topics: Optional chapter ids to restrict to.
        seed: Optional RNG seed for reproducibility.
        membership_ratio: Rough fraction (0..1) of questions that should be
            auto-generated membership items; the rest are conceptual.

    Returns:
        A shuffled list of up to ``total`` :class:`Question` objects, drawn
        as evenly as possible across the chosen topics.
    """
    rng = random.Random(seed)
    chosen_topics = list(topics) if topics else list(TOPICS)
    chosen_topics = [t for t in chosen_topics if t in TOPICS]
    if not chosen_topics or total <= 0:
        return []

    want_membership = max(0, min(total, round(total * membership_ratio)))
    want_concept = total - want_membership

    # Conceptual pool, grouped by topic for balanced round-robin draws.
    concept_by_topic: Dict[str, List[Question]] = {
        t: concept_questions(t) for t in chosen_topics
    }
    for lst in concept_by_topic.values():
        rng.shuffle(lst)

    # Membership pool (generate generously, then round-robin by topic).
    mem_seed = None if seed is None else seed + 1
    mem_all = generate_membership_questions(
        want_membership * 3 + len(chosen_topics) * 2,
        chapters=chosen_topics, seed=mem_seed,
    )
    mem_by_topic: Dict[str, List[Question]] = {t: [] for t in chosen_topics}
    for q in mem_all:
        if q.topic in mem_by_topic:
            mem_by_topic[q.topic].append(q)

    def _round_robin(buckets: Dict[str, List[Question]],
                     want: int) -> List[Question]:
        out: List[Question] = []
        order = list(buckets.keys())
        idx = {t: 0 for t in order}
        progressed = True
        while len(out) < want and progressed:
            progressed = False
            for t in order:
                if len(out) >= want:
                    break
                i = idx[t]
                if i < len(buckets[t]):
                    out.append(buckets[t][i])
                    idx[t] = i + 1
                    progressed = True
        return out

    picked = _round_robin(concept_by_topic, want_concept)
    picked += _round_robin(mem_by_topic, want_membership)

    # If one pool was short, top up from the other to reach `total`.
    if len(picked) < total:
        chosen_ids = {q.qid for q in picked}
        leftovers: List[Question] = []
        for bucket in (concept_by_topic, mem_by_topic):
            for lst in bucket.values():
                for q in lst:
                    if q.qid not in chosen_ids:
                        leftovers.append(q)
        rng.shuffle(leftovers)
        picked += leftovers[: total - len(picked)]

    rng.shuffle(picked)
    return picked[:total]


class ExamSession:
    """A gradeable, optionally timed practice exam.

    The session owns a fixed list of :class:`Question` objects, records the
    student's answers, and reports scores overall and per topic. It never
    blocks on the clock; timing is purely informational via
    :meth:`seconds_remaining` and :meth:`is_expired`.

    Typical use::

        session = ExamSession(questions, time_limit=600)
        session.answer(questions[0].qid, 1)
        correct, total = session.score()
        weak = recommended_focus(session)

    Args:
        questions: The questions for this session (order preserved).
        time_limit: Optional limit in seconds; None means untimed.
        clock: Monotonic time source (seconds). Injectable for testing;
            defaults to :func:`time.monotonic`.
    """

    def __init__(
        self,
        questions: Sequence[Question],
        time_limit: Optional[float] = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._clock = clock
        self.questions: List[Question] = list(questions)
        self._by_id: Dict[str, Question] = {q.qid: q for q in self.questions}
        self.time_limit: Optional[float] = time_limit
        self.start_time: float = clock()
        # qid -> AnswerRecord
        self.answers: Dict[str, AnswerRecord] = {}

    # -- construction convenience ---------------------------------------
    @classmethod
    def mixed(
        cls,
        total: int,
        topics: Optional[Sequence[str]] = None,
        time_limit: Optional[float] = None,
        seed: Optional[int] = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> "ExamSession":
        """Build a session from a freshly assembled balanced mixed quiz."""
        questions = build_mixed_quiz(total, topics=topics, seed=seed)
        return cls(questions, time_limit=time_limit, clock=clock)

    # -- timing (non-blocking) ------------------------------------------
    def elapsed(self) -> float:
        """Seconds elapsed since the session started."""
        return self._clock() - self.start_time

    def seconds_remaining(self) -> Optional[float]:
        """Seconds left before the time limit, or None if untimed.

        Never negative — a finished clock reports 0.0.
        """
        if self.time_limit is None:
            return None
        return max(0.0, self.time_limit - self.elapsed())

    def is_expired(self) -> bool:
        """True iff a time limit is set and has been reached."""
        remaining = self.seconds_remaining()
        return remaining is not None and remaining <= 0.0

    # -- answering -------------------------------------------------------
    def answer(self, qid: str, choice: object) -> bool:
        """Record and grade one answer.

        Args:
            qid: The :attr:`Question.qid` being answered.
            choice: The student's choice (index, bool, or option text).

        Returns:
            True iff the recorded answer is correct.

        Raises:
            KeyError: if ``qid`` is not part of this session.
        """
        question = self._by_id[qid]
        correct = question.is_correct(choice)
        self.answers[qid] = AnswerRecord(question, choice, correct)
        return correct

    def answered_count(self) -> int:
        """How many questions have been answered so far."""
        return len(self.answers)

    def remaining_questions(self) -> List[Question]:
        """Questions in this session that have not yet been answered."""
        return [q for q in self.questions if q.qid not in self.answers]

    # -- scoring ---------------------------------------------------------
    def score(self) -> Tuple[int, int]:
        """Return ``(correct, total)`` over all questions in the session.

        ``total`` is the number of questions in the session (unanswered
        questions count against the student, as on a real exam).
        """
        correct = sum(1 for r in self.answers.values() if r.correct)
        return correct, len(self.questions)

    def score_fraction(self) -> float:
        """Correct answers as a fraction of total (0.0 if empty)."""
        correct, total = self.score()
        return correct / total if total else 0.0

    def summary_by_topic(self) -> Dict[str, Tuple[int, int]]:
        """Per-topic ``(correct, total)`` tallies.

        Includes every topic that appears in the session's questions, so a
        student can see which chapters are weak. Unanswered questions count
        toward the topic total but not toward correct.
        """
        totals: Dict[str, int] = {}
        correct: Dict[str, int] = {}
        for q in self.questions:
            totals[q.topic] = totals.get(q.topic, 0) + 1
            correct.setdefault(q.topic, 0)
        for r in self.answers.values():
            if r.correct:
                topic = r.question.topic
                correct[topic] = correct.get(topic, 0) + 1
        return {t: (correct.get(t, 0), totals[t]) for t in totals}

    def review(self) -> List[Tuple[Question, object, bool, str]]:
        """Build a review list for every question in the session.

        Returns:
            A list of ``(question, their_answer, correct, explanation)``
            tuples in session order. For an unanswered question,
            ``their_answer`` is None and ``correct`` is False.
        """
        rows: List[Tuple[Question, object, bool, str]] = []
        for q in self.questions:
            rec = self.answers.get(q.qid)
            if rec is None:
                rows.append((q, None, False, q.explanation))
            else:
                rows.append((q, rec.given, rec.correct, q.explanation))
        return rows


# ---------------------------------------------------------------------- #
# Study guidance
# ---------------------------------------------------------------------- #
def recommended_focus(
    session: ExamSession,
    max_topics: int = 3,
    threshold: float = 1.0,
) -> List[str]:
    """Suggest chapter ids the student should review, weakest first.

    A topic is a candidate when its per-topic accuracy is strictly below
    ``threshold`` (default 1.0, i.e. anything less than perfect). Candidates
    are sorted by accuracy ascending (weakest first), breaking ties by the
    number of missed questions and then by chapter order in :data:`TOPICS`.

    Args:
        session: The session to analyze.
        max_topics: Maximum number of chapter ids to return.
        threshold: Accuracy below which a topic is considered weak.

    Returns:
        Up to ``max_topics`` chapter ids, weakest first. Empty if the
        student scored at/above ``threshold`` on every topic.
    """
    summary = session.summary_by_topic()

    def topic_rank(cid: str) -> int:
        return TOPICS.index(cid) if cid in TOPICS else len(TOPICS)

    scored: List[Tuple[float, int, int, str]] = []
    for topic, (correct, total) in summary.items():
        if total == 0:
            continue
        accuracy = correct / total
        if accuracy < threshold:
            missed = total - correct
            scored.append((accuracy, -missed, topic_rank(topic), topic))

    scored.sort()
    return [topic for (_acc, _miss, _rank, topic) in scored[:max_topics]]


# ---------------------------------------------------------------------- #
# Public API summary (for humans and the GUI layer)
# ---------------------------------------------------------------------- #
__all__ = [
    "TOPICS",
    "Question",
    "AnswerRecord",
    "ExamSession",
    "CONCEPT_QUESTIONS",
    "concept_questions",
    "concept_counts_by_topic",
    "generate_membership_questions",
    "build_mixed_quiz",
    "recommended_focus",
]
