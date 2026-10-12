"""
lessons.py
----------
Concise, exam-focused teaching content for Automata Tutor, scoped to Sipser
*Introduction to the Theory of Computation*, Chapter 1 (DFAs, NFAs,
ε-transitions, regular expressions, and NFA→DFA conversion).

Everything here is pure standard library (no tkinter) so it can be imported by
the GUI, a CLI, or a test harness. Chapter ids match curriculum.py exactly:
    dfa, nfa, epsilon, regex, convert

Four public pieces:
    CHEAT_SHEETS           — dict[str, list[str]]        : punchy fact bullets
    WORKED_EXAMPLES        — dict[str, list[WorkedExample]] : solved problems
    SUBSET_CONSTRUCTION_DEMO + run_subset_construction()  : real NFA→DFA trace
    EXAM_TIPS              — list[str]                    : test-taking advice

All prose is in our own words; Sipser sections are cited, never quoted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from automaton import Automaton, EPSILON


# ====================================================================== #
# 1. Cheat sheets — must-know facts per chapter (5–9 one-line bullets)
# ====================================================================== #
CHEAT_SHEETS: Dict[str, List[str]] = {
    "dfa": [
        "DFA = (Q, Σ, δ, q0, F); δ is TOTAL: exactly one move per (state, symbol). (§1.1)",
        "Deterministic = no choices, no gaps — every state has an arrow for every symbol.",
        "Accept iff the run ENDS in a state of F; the path is unique for a given string.",
        "A state = the one bounded fact you must remember (parity, last k symbols, pattern progress).",
        "Empty string ε is accepted iff q0 ∈ F.",
        "Need a 'dead'/trap state to absorb strings that fall out of the pattern.",
        "|Q| is fixed, so a DFA cannot count unboundedly (that is why aⁿbⁿ is not regular).",
        "Language L(M) = the set of strings M accepts; two DFAs are equivalent iff L is equal.",
    ],
    "nfa": [
        "NFA = (Q, Σ, δ, q0, F) but δ(state, symbol) returns a SET of states (0, 1, or many). (§1.2)",
        "Accept iff AT LEAST ONE computation path ends in an accepting state.",
        "Nondeterminism = 'guess and verify'; a dead path just fails, it does not reject the whole run.",
        "No arrow on a symbol is allowed — that branch simply dies.",
        "NFAs are often exponentially smaller than the equivalent DFA for the same language.",
        "Classic win: 'k-th symbol from the END is 1' — tiny NFA, big DFA.",
        "Same expressive power as DFAs: both recognize exactly the regular languages.",
        "Simulating an NFA = tracking the SET of currently-possible states.",
    ],
    "epsilon": [
        "ε-transition = jump to another state WITHOUT reading input (a free move). (§1.2)",
        "ε-closure(S) = S plus every state reachable from S using only ε-arrows (include S itself).",
        "Simulation step: move on the symbol, THEN take ε-closure of the result.",
        "Start configuration = ε-closure({q0}), not just {q0}.",
        "ε-moves make gluing machines trivial — the backbone of regex→NFA (Thompson). (§1.3)",
        "Adding ε adds NO power: every ε-NFA has an equivalent ε-free NFA and DFA.",
        "A state is accepting-by-ε if its ε-closure contains an accept state.",
        "Compute ε-closure as a fixpoint/BFS: keep adding ε-successors until nothing new appears.",
    ],
    "regex": [
        "Three operators: union a|b (either), concatenation ab (then), Kleene star a* (0+ repeats). (§1.3)",
        "Precedence HIGH→LOW: star  >  concatenation  >  union — like exponent, multiply, add.",
        "a|bc* parses as a | (b(c*)), NOT (a|b)(c*) — parenthesize when in doubt.",
        "a* includes the empty string ε; a+ = aa* means one or more.",
        "∅ = the empty language (no strings); ε = the language {empty string}; they differ.",
        "(0|1)* = all binary strings; append a literal to pin an ending: (0|1)*01.",
        "Regex, NFA, and DFA all describe exactly the regular languages — three views, one class.",
        "Converting regex→NFA uses ε-glue; NFA→regex uses state elimination (GNFA).",
    ],
    "convert": [
        "Subset construction: each DFA state is a SET of NFA states the NFA could be in. (§1.2)",
        "DFA start = ε-closure({NFA start}).",
        "DFA move: δ'(S, a) = ε-closure( union of δ(q, a) for every q in S ).",
        "DFA accepts a subset S iff S contains ANY NFA accept state.",
        "Stop when no NEW subsets appear; reachable DFA states ≤ 2^n but usually far fewer.",
        "The empty set ∅ is the dead/trap state — route 'no moves' there and loop it on all symbols.",
        "Resulting DFA is TOTAL and deterministic by construction, and L(DFA) = L(NFA).",
        "Equivalence triangle: DFA ≡ NFA ≡ regex — convert freely among all three. (§1.2–§1.3)",
    ],
}


# ====================================================================== #
# 2. Worked examples
# ====================================================================== #
@dataclass(frozen=True)
class WorkedExample:
    """A fully solved problem walked through step by step.

    steps is a list of (heading, explanation) pairs, each one a discrete move
    in the reasoning so the GUI can reveal them one at a time.
    """
    title: str
    prompt: str
    steps: List[Tuple[str, str]] = field(default_factory=list)


WORKED_EXAMPLES: Dict[str, List[WorkedExample]] = {
    "dfa": [
        WorkedExample(
            title="DFA for 'even number of 0s' over {0,1}",
            prompt="Build a DFA accepting binary strings that contain an even "
                   "count of 0s (1s do not matter).",
            steps=[
                ("1. Decide what to remember",
                 "The only fact that matters is the parity of 0s seen so far. "
                 "That is one bit, so two states suffice: EVEN and ODD."),
                ("2. Pick start and accept",
                 "Before reading anything, zero 0s is even, so EVEN is the "
                 "start state and also the single accept state."),
                ("3. Wire the transitions",
                 "Reading 1 never changes parity: EVEN--1-->EVEN, ODD--1-->ODD. "
                 "Reading 0 flips it: EVEN--0-->ODD, ODD--0-->EVEN."),
                ("4. Check totality",
                 "Both states have exactly one arrow for 0 and one for 1, so δ "
                 "is total — this is a legal DFA with no dead state needed."),
                ("5. Sanity test",
                 "'' → EVEN (accept). '00' → ODD → EVEN (accept). '0' → ODD "
                 "(reject). '010' → ODD→ODD→EVEN... recount: 0→ODD, 1→ODD, "
                 "0→EVEN (accept, two 0s). Correct."),
            ],
        ),
    ],
    "nfa": [
        WorkedExample(
            title="NFA for 'third symbol from the end is 1'",
            prompt="Build a small NFA over {0,1} accepting strings whose "
                   "third-from-last symbol is 1.",
            steps=[
                ("1. Use nondeterminism to guess",
                 "Stay in start state q0 reading anything (loop on 0 and 1), "
                 "guessing when the crucial 1 arrives."),
                ("2. Lay down the tail",
                 "From q0, on a 1, move to q1 (this guesses 'this 1 is third "
                 "from the end'). q1--0,1-->q2, q2--0,1-->q3."),
                ("3. Mark the accept state",
                 "q3 is accepting. Reaching q3 means exactly two symbols "
                 "followed the guessed 1, i.e. it was third from the end."),
                ("4. Why a dead guess is harmless",
                 "If the machine guesses the wrong 1, that branch runs off the "
                 "end before q3 or overshoots and dies — but some other branch "
                 "guesses correctly, and acceptance needs only ONE good path."),
                ("5. Note the size win",
                 "This NFA has 4 states; the equivalent DFA must track the last "
                 "3 symbols and needs 8 states. Nondeterminism pays off."),
            ],
        ),
    ],
    "epsilon": [
        WorkedExample(
            title="ε-closure and a glued union",
            prompt="Given start s with s--ε-->a and a--ε-->b, and separately "
                   "b--1-->f, compute the start configuration and run on '1'.",
            steps=[
                ("1. Compute ε-closure of the start",
                 "ε-closure({s}) follows free arrows: s reaches a, a reaches b. "
                 "So the start configuration is {s, a, b}."),
                ("2. Read the symbol '1'",
                 "From the active set {s, a, b}, only b has a 1-arrow: b--1-->f. "
                 "The moved set is {f}."),
                ("3. Take ε-closure again",
                 "f has no outgoing ε-arrows, so ε-closure({f}) = {f}. The new "
                 "active set is {f}."),
                ("4. Decide acceptance",
                 "If f is an accept state, '1' is accepted. The ε-moves let us "
                 "stitch 's' to 'b' for free before any symbol was read."),
                ("5. Takeaway",
                 "Always ε-close the start AND ε-close after every symbol — "
                 "forgetting either is the most common ε simulation bug."),
            ],
        ),
    ],
    "regex": [
        WorkedExample(
            title="Reading (0|1)*01 and a precedence trap",
            prompt="Describe the language of (0|1)*01, then explain why "
                   "0|1* is different from (0|1)*.",
            steps=[
                ("1. Parse the star block",
                 "(0|1)* means zero or more copies of 'either 0 or 1' — i.e. "
                 "any binary string, including the empty one."),
                ("2. Concatenate the suffix",
                 "Following it with 01 forces the string to END in 01. So the "
                 "language is 'all binary strings ending in 01'."),
                ("3. Smallest members",
                 "The shortest accepted string is '01' (the star part is "
                 "empty). '0101', '1101', '00001' all qualify."),
                ("4. The precedence trap",
                 "Star binds tighter than union, so 0|1* parses as 0 | (1*): "
                 "the single string '0' OR any run of 1s (including ε). That is "
                 "NOT the same as (0|1)*."),
                ("5. Rule of thumb",
                 "When a star should cover a choice, you MUST parenthesize the "
                 "choice first: (0|1)*. Precedence is star > concat > union."),
            ],
        ),
    ],
    "convert": [
        WorkedExample(
            title="NFA→DFA by subset construction (with an ε-move)",
            prompt="Convert this ε-NFA over {0,1} to a DFA by subset "
                   "construction. States A,B,C,D. Start A (also A--ε-->C). "
                   "Transitions: A--0-->B, A--ε-->C, B--1-->D, C--0-->C, "
                   "C--1-->D, D--0-->D, D--1-->D. Accept state: D.",
            steps=[
                ("1. Compute the DFA start = ε-closure({A})",
                 "A has A--ε-->C, and C has no further ε-arrows. So the start "
                 "DFA state is the subset {A, C}. Call it S0 = {A,C}."),
                ("2. S0 on 0",
                 "Move on 0 from {A,C}: A--0-->B and C--0-->C, giving {B,C}. "
                 "ε-close {B,C} = {B,C} (no ε-arrows). New DFA state S1={B,C}."),
                ("3. S0 on 1",
                 "Move on 1 from {A,C}: A has no 1-arrow, C--1-->D, giving {D}. "
                 "ε-close {D} = {D}. New DFA state S2={D}."),
                ("4. S1={B,C} on each symbol",
                 "On 0: B has none, C--0-->C → {C}; ε-close = {C} → new S3={C}. "
                 "On 1: B--1-->D, C--1-->D → {D} = S2 (already seen)."),
                ("5. S2={D} on each symbol",
                 "D--0-->D and D--1-->D, so on 0→{D}=S2 and on 1→{D}=S2. S2 "
                 "self-loops on both symbols — it is a sink."),
                ("6. S3={C} on each symbol",
                 "C--0-->C → {C}=S3 on 0; C--1-->D → {D}=S2 on 1. No new "
                 "subsets are produced."),
                ("7. No new subsets — stop",
                 "Reachable DFA states: S0={A,C}, S1={B,C}, S2={D}, S3={C}. "
                 "Every (state,symbol) now lands in a known subset, so we halt."),
                ("8. Mark accepting subsets",
                 "A subset accepts iff it contains the NFA accept state D. Only "
                 "S2={D} contains D, so S2 is the single DFA accept state."),
                ("9. Final DFA transition table",
                 "States {S0,S1,S2,S3}, start S0, accept {S2}. "
                 "S0:0→S1,1→S2 | S1:0→S3,1→S2 | S2:0→S2,1→S2 | S3:0→S3,1→S2. "
                 "The DFA is total and recognizes the same language as the NFA."),
            ],
        ),
    ],
}


# ====================================================================== #
# 3. Subset-construction demo + real engine
# ====================================================================== #
# A concrete small ε-NFA over {0,1}. This matches the 'convert' worked
# example above so the GUI can animate the exact trace students just read.
#   A -0-> B,  A -ε-> C,  B -1-> D,
#   C -0-> C,  C -1-> D,  D -0-> D,  D -1-> D
# Start: A.  Accept: D.
SUBSET_CONSTRUCTION_DEMO: Dict[str, object] = {
    "states": ["A", "B", "C", "D"],
    "start": "A",
    "accept": ["D"],
    "alphabet": ["0", "1"],
    "transitions": [
        ["A", "0", "B"],
        ["A", EPSILON, "C"],
        ["B", "1", "D"],
        ["C", "0", "C"],
        ["C", "1", "D"],
        ["D", "0", "D"],
        ["D", "1", "D"],
    ],
}


def _build_nfa(nfa_spec: Dict[str, object]) -> Automaton:
    """Construct an Automaton from a subset-construction spec dict."""
    nfa = Automaton()
    start = nfa_spec["start"]
    accept = set(nfa_spec["accept"])  # type: ignore[arg-type]
    for name in nfa_spec["states"]:  # type: ignore[union-attr]
        nfa.add_state(
            name,
            is_start=(name == start),
            is_accept=(name in accept),
        )
    for src, sym, dst in nfa_spec["transitions"]:  # type: ignore[union-attr]
        nfa.add_transition(src, sym, dst)
    return nfa


def run_subset_construction(nfa_spec: Dict[str, object]) -> Dict[str, object]:
    """Compute the subset construction of an ε-NFA into a DFA.

    Builds a real automaton.Automaton from `nfa_spec`, then performs the
    classic subset (powerset) construction using epsilon_closure and the
    transition logic. Returns a structured trace the GUI can animate.

    Returns a dict with:
        "nfa"            : the built Automaton (source NFA)
        "alphabet"       : sorted list of input symbols
        "dfa_states"     : ordered list of DFA states, each a sorted tuple of
                           NFA state names (empty tuple = dead/trap state)
        "start"          : the start DFA state (sorted tuple)
        "accept"         : set of accepting DFA states (sorted tuples)
        "transitions"    : dict {(dfa_state, symbol): dfa_state}
    """
    nfa = _build_nfa(nfa_spec)
    alphabet = sorted(str(s) for s in nfa_spec["alphabet"])  # type: ignore[union-attr]
    nfa_accept = nfa.accept_states()

    def closure_tuple(states: set) -> Tuple[str, ...]:
        return tuple(sorted(nfa.epsilon_closure(states)))

    start_state = nfa.start_state()
    assert start_state is not None, "NFA spec has no start state"
    start_dfa = closure_tuple({start_state})

    dfa_states: List[Tuple[str, ...]] = [start_dfa]
    seen = {start_dfa}
    transitions: Dict[Tuple[Tuple[str, ...], str], Tuple[str, ...]] = {}

    # Worklist (BFS) over reachable subsets.
    queue: List[Tuple[str, ...]] = [start_dfa]
    while queue:
        current = queue.pop(0)
        for sym in alphabet:
            moved: set = set()
            for q in current:
                moved |= nfa.moves(q, sym)
            target = closure_tuple(moved)  # empty tuple if nothing moved
            transitions[(current, sym)] = target
            if target not in seen:
                seen.add(target)
                dfa_states.append(target)
                queue.append(target)

    accept = {s for s in dfa_states if set(s) & nfa_accept}

    return {
        "nfa": nfa,
        "alphabet": alphabet,
        "dfa_states": dfa_states,
        "start": start_dfa,
        "accept": accept,
        "transitions": transitions,
    }


def _dfa_from_construction(result: Dict[str, object]) -> Automaton:
    """Materialize the subset-construction result as a real DFA Automaton.

    Used for verification: lets us simulate the produced DFA with the same
    engine as the source NFA and compare languages.
    """
    dfa = Automaton()
    start = result["start"]
    accept_states = result["accept"]  # type: ignore[assignment]

    def label(state: Tuple[str, ...]) -> str:
        # Deterministic string name for a subset; {} marks the dead state.
        return "{" + ",".join(state) + "}" if state else "{}"

    for state in result["dfa_states"]:  # type: ignore[union-attr]
        dfa.add_state(
            label(state),
            is_start=(state == start),
            is_accept=(state in accept_states),  # type: ignore[operator]
        )
    for (src, sym), dst in result["transitions"].items():  # type: ignore[union-attr]
        dfa.add_transition(label(src), sym, label(dst))
    return dfa


def verify_subset_construction(nfa_spec: Dict[str, object],
                               max_len: int = 10) -> Tuple[bool, str]:
    """Check that the subset-construction DFA matches the source NFA language.

    Simulates both machines on every binary string up to `max_len` and
    compares accept/reject verdicts. Returns (ok, message); on mismatch the
    message names the first differing string.
    """
    result = run_subset_construction(nfa_spec)
    nfa = result["nfa"]  # type: ignore[assignment]
    dfa = _dfa_from_construction(result)
    alphabet = result["alphabet"]  # type: ignore[assignment]

    tested = 0
    for length in range(max_len + 1):
        for word in _all_words(alphabet, length):  # type: ignore[arg-type]
            tested += 1
            if nfa.simulate(word).accepted != dfa.simulate(word).accepted:  # type: ignore[union-attr]
                return (False,
                        f"Mismatch on '{word or 'ε'}': "
                        f"NFA={nfa.simulate(word).accepted}, "  # type: ignore[union-attr]
                        f"DFA={dfa.simulate(word).accepted}.")
    return (True, f"DFA ≡ NFA on all {tested} strings up to length {max_len}.")


def _all_words(alphabet: List[str], length: int) -> List[str]:
    """All strings of exactly `length` over `alphabet` (length 0 → ['']) ."""
    if length == 0:
        return [""]
    shorter = _all_words(alphabet, length - 1)
    return [w + a for w in shorter for a in alphabet]


# ====================================================================== #
# 4. Exam tips
# ====================================================================== #
EXAM_TIPS: List[str] = [
    "Design DFA states by asking 'what is the minimum I must remember?' — "
    "parity, last k symbols, or how far into a pattern you are.",
    "Make DFAs TOTAL: add a dead/trap state and route every missing arrow to "
    "it, or you have not drawn a valid DFA.",
    "Sanity-check any NFA by testing the shortest accepted and shortest "
    "rejected strings, plus the empty string ε.",
    "In subset construction, ALWAYS ε-close: once for the start set and once "
    "after every symbol — the #1 lost-point error.",
    "Treat the empty set ∅ as the dead DFA state; give it self-loops on every "
    "symbol so the DFA stays total.",
    "Regex precedence is star > concatenation > union; parenthesize a choice "
    "before starring it, or 0|1* bites you.",
    "Remember ∅ ≠ ε: ∅ accepts nothing, ε accepts only the empty string — and "
    "a* always includes ε.",
    "For 'k-th from the end' languages, build an NFA (guess the spot); convert "
    "only if the question demands a DFA.",
    "Only reachable subsets become DFA states — do not enumerate all 2^n; grow "
    "them from the start by BFS.",
    "To prove a language is NOT regular, reach for the pumping lemma, not a "
    "bigger DFA (finite memory cannot count unboundedly).",
]
