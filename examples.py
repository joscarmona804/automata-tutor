"""
examples.py
-----------
Verified, drawable *example answers* for the automata-construction problems in
``quiz.py``.

The game GUI can call :func:`get_example` with a problem key and, if an example
exists, receive a small finite automaton laid out as fractions of the canvas.
Drawing that automaton shows the student one concrete, *correct* recognizer of
the problem's language:

  * For a DFA/NFA build problem the example is a correct machine of that kind.
  * For an RE problem the example is an automaton equivalent to the regex
    (the picture a student would draw if asked to realise the language).
  * For a conversion problem the example is a correct *target* automaton
    (the thing the student is asked to produce), not the given source.

Every spec in :data:`EXAMPLE_SPECS` has been brute-force verified to accept
EXACTLY the problem's language over all binary strings up to length 8, using
:func:`verify_example`. See the module-level constant docstring for the spec
shape.

This module is pure standard library and contains no GUI/tkinter code.
"""

from __future__ import annotations

from itertools import product
from typing import Dict, List, Optional, Tuple

from automaton import Automaton, EPSILON
from quiz import Problem, get_problem

# ---------------------------------------------------------------------- #
# Spec shape
# ---------------------------------------------------------------------- #
# A spec is a plain dict (JSON-friendly) with the following keys:
#
#   {
#     "states": [
#         {"name": "q0", "x": 0.18, "y": 0.5, "start": True, "accept": False},
#         ...
#     ],
#     "transitions": [["q0", "0", "q0"], ["q0", "1", "q1"], ...],  # ε == "ε"
#     "alphabet": ["0", "1"],
#     "caption": "one short line describing what to notice",
#   }
#
# x and y are FRACTIONS in [0, 1] of the drawing canvas; the GUI scales them to
# pixels. States are laid out left-to-right: the start state sits on the left
# (~0.15) and accepting states tend toward the right, with y spread between
# roughly 0.3 and 0.7 so edges and rings do not overlap.
Spec = Dict[str, object]


# ---------------------------------------------------------------------- #
# The example bank, keyed by Problem.key
# ---------------------------------------------------------------------- #
EXAMPLE_SPECS: Dict[str, Spec] = {

    # ================================================================== #
    # chapter: dfa
    # ================================================================== #

    # (#1's ≡ 1 mod 3) OR (odd number of 0's): product DFA, 6 states.
    # State r_p = (ones mod 3, zeros mod 2). '1' advances r, '0' flips p.
    # Accept when r == 1 OR p == 1.
    "dfa_mod3_1_or_odd0": {
        "states": [
            {"name": "00", "x": 0.14, "y": 0.30, "start": True,  "accept": False},
            {"name": "01", "x": 0.14, "y": 0.70, "start": False, "accept": True},
            {"name": "10", "x": 0.50, "y": 0.30, "start": False, "accept": True},
            {"name": "11", "x": 0.50, "y": 0.70, "start": False, "accept": True},
            {"name": "20", "x": 0.86, "y": 0.30, "start": False, "accept": False},
            {"name": "21", "x": 0.86, "y": 0.70, "start": False, "accept": True},
        ],
        "transitions": [
            ["00", "1", "10"], ["00", "0", "01"],
            ["01", "1", "11"], ["01", "0", "00"],
            ["10", "1", "20"], ["10", "0", "11"],
            ["11", "1", "21"], ["11", "0", "10"],
            ["20", "1", "00"], ["20", "0", "21"],
            ["21", "1", "01"], ["21", "0", "20"],
        ],
        "alphabet": ["0", "1"],
        "caption": "State = (#1 mod 3, #0 mod 2); accept if either coordinate "
                   "is 1 (OR), so 4 of 6 states are accepting.",
    },

    # Same product machine, AND: accept only the single state (1,1).
    "dfa_mod3_1_and_odd0": {
        "states": [
            {"name": "00", "x": 0.14, "y": 0.30, "start": True,  "accept": False},
            {"name": "01", "x": 0.14, "y": 0.70, "start": False, "accept": False},
            {"name": "10", "x": 0.50, "y": 0.30, "start": False, "accept": False},
            {"name": "11", "x": 0.50, "y": 0.70, "start": False, "accept": True},
            {"name": "20", "x": 0.86, "y": 0.30, "start": False, "accept": False},
            {"name": "21", "x": 0.86, "y": 0.70, "start": False, "accept": False},
        ],
        "transitions": [
            ["00", "1", "10"], ["00", "0", "01"],
            ["01", "1", "11"], ["01", "0", "00"],
            ["10", "1", "20"], ["10", "0", "11"],
            ["11", "1", "21"], ["11", "0", "10"],
            ["20", "1", "00"], ["20", "0", "21"],
            ["21", "1", "01"], ["21", "0", "20"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Same 6 states as the OR version; AND accepts only (1,1), "
                   "the single double-ringed state.",
    },

    # (#1's ≡ 1 mod 3) OR (odd #1's): both tests measure #1's, so track
    # #1's mod 6. '0' self-loops; '1' advances. Accept {c1,c3,c4,c5}.
    "dfa_mod3_1_or_odd1": {
        "states": [
            {"name": "c0", "x": 0.12, "y": 0.50, "start": True,  "accept": False},
            {"name": "c1", "x": 0.27, "y": 0.30, "start": False, "accept": True},
            {"name": "c2", "x": 0.42, "y": 0.70, "start": False, "accept": False},
            {"name": "c3", "x": 0.57, "y": 0.30, "start": False, "accept": True},
            {"name": "c4", "x": 0.72, "y": 0.70, "start": False, "accept": True},
            {"name": "c5", "x": 0.88, "y": 0.30, "start": False, "accept": True},
        ],
        "transitions": [
            ["c0", "1", "c1"], ["c0", "0", "c0"],
            ["c1", "1", "c2"], ["c1", "0", "c1"],
            ["c2", "1", "c3"], ["c2", "0", "c2"],
            ["c3", "1", "c4"], ["c3", "0", "c3"],
            ["c4", "1", "c5"], ["c4", "0", "c4"],
            ["c5", "1", "c0"], ["c5", "0", "c5"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Count #1's mod 6 (0's self-loop); accept c1,c3,c4,c5 where "
                   "i≡1 mod 3 OR i is odd.",
    },

    # Odd length OR s = "01": minimal 5-state DFA.
    "dfa_oddlen_or_01": {
        "states": [
            {"name": "Seps", "x": 0.12, "y": 0.50, "start": True,  "accept": False},
            {"name": "S0",   "x": 0.37, "y": 0.25, "start": False, "accept": True},
            {"name": "S1",   "x": 0.37, "y": 0.75, "start": False, "accept": True},
            {"name": "S01",  "x": 0.63, "y": 0.25, "start": False, "accept": True},
            {"name": "S00",  "x": 0.63, "y": 0.75, "start": False, "accept": False},
        ],
        "transitions": [
            ["Seps", "0", "S0"], ["Seps", "1", "S1"],
            ["S0",   "0", "S00"], ["S0",  "1", "S01"],
            ["S1",   "0", "S00"], ["S1",  "1", "S00"],
            ["S00",  "0", "S1"],  ["S00", "1", "S1"],
            ["S01",  "0", "S1"],  ["S01", "1", "S1"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Minimal 5-state DFA: S0,S1,S01 accept; after the 01-corridor "
                   "S00/S1 just track odd length.",
    },

    # Odd #0's OR s = "001": minimal 6-state DFA.
    "dfa_odd0_or_001": {
        "states": [
            {"name": "Seps", "x": 0.12, "y": 0.50, "start": True,  "accept": False},
            {"name": "S0",   "x": 0.33, "y": 0.22, "start": False, "accept": True},
            {"name": "S1",   "x": 0.33, "y": 0.78, "start": False, "accept": False},
            {"name": "S00",  "x": 0.58, "y": 0.22, "start": False, "accept": False},
            {"name": "S01",  "x": 0.58, "y": 0.78, "start": False, "accept": True},
            {"name": "S001", "x": 0.86, "y": 0.50, "start": False, "accept": True},
        ],
        "transitions": [
            ["Seps", "0", "S0"],  ["Seps", "1", "S1"],
            ["S0",   "0", "S00"], ["S0",   "1", "S01"],
            ["S1",   "0", "S01"], ["S1",   "1", "S1"],
            ["S00",  "0", "S01"], ["S00",  "1", "S001"],
            ["S01",  "0", "S1"],  ["S01",  "1", "S01"],
            ["S001", "0", "S01"], ["S001", "1", "S1"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Minimal 6-state DFA; S001 is the exact-'001' accept, and "
                   "S1/S01 settle into a 0-parity tracker.",
    },

    # Third symbol is 1 (length >= 3): count first three positions.
    "dfa_third_symbol_1": {
        "states": [
            {"name": "q0", "x": 0.12, "y": 0.50, "start": True,  "accept": False},
            {"name": "q1", "x": 0.32, "y": 0.50, "start": False, "accept": False},
            {"name": "q2", "x": 0.52, "y": 0.50, "start": False, "accept": False},
            {"name": "qA", "x": 0.80, "y": 0.28, "start": False, "accept": True},
            {"name": "qD", "x": 0.80, "y": 0.72, "start": False, "accept": False},
        ],
        "transitions": [
            ["q0", "0", "q1"], ["q0", "1", "q1"],
            ["q1", "0", "q2"], ["q1", "1", "q2"],
            ["q2", "1", "qA"], ["q2", "0", "qD"],
            ["qA", "0", "qA"], ["qA", "1", "qA"],
            ["qD", "0", "qD"], ["qD", "1", "qD"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Read two symbols blindly; the 3rd routes to accepting qA "
                   "(if 1) or dead qD (if 0).",
    },

    # Does NOT end in 00: 3-state suffix tracker, accept all but q00.
    "dfa_not_end_00": {
        "states": [
            {"name": "qS",  "x": 0.16, "y": 0.35, "start": True,  "accept": True},
            {"name": "qZ",  "x": 0.52, "y": 0.65, "start": False, "accept": True},
            {"name": "q00", "x": 0.86, "y": 0.35, "start": False, "accept": False},
        ],
        "transitions": [
            ["qS",  "1", "qS"],  ["qS",  "0", "qZ"],
            ["qZ",  "1", "qS"],  ["qZ",  "0", "q00"],
            ["q00", "1", "qS"],  ["q00", "0", "q00"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Track the trailing run of 0's; only q00 (ends in 00) is "
                   "non-accepting.",
    },

    # Contains 00 AND contains 11: this is the MINIMAL DFA, which needs 8
    # states (no correct DFA is smaller), so it is the one example that
    # exceeds the usual 6-state layout budget. State names encode the last
    # symbol read and the two sticky flags seen00 / seen11.
    "dfa_contains_00_and_11": {
        "states": [
            {"name": "start", "x": 0.06, "y": 0.50, "start": True,  "accept": False},
            {"name": "s0",    "x": 0.24, "y": 0.26, "start": False, "accept": False},
            {"name": "s1",    "x": 0.24, "y": 0.74, "start": False, "accept": False},
            {"name": "h00a",  "x": 0.46, "y": 0.14, "start": False, "accept": False},
            {"name": "h00b",  "x": 0.68, "y": 0.26, "start": False, "accept": False},
            {"name": "h11a",  "x": 0.46, "y": 0.86, "start": False, "accept": False},
            {"name": "h11b",  "x": 0.68, "y": 0.74, "start": False, "accept": False},
            {"name": "both",  "x": 0.92, "y": 0.50, "start": False, "accept": True},
        ],
        "transitions": [
            # start: remember the first symbol, no pair yet.
            ["start", "0", "s0"], ["start", "1", "s1"],
            # s0 = last 0, no pair yet; s1 = last 1, no pair yet.
            ["s0", "0", "h00a"], ["s0", "1", "s1"],
            ["s1", "0", "s0"], ["s1", "1", "h11a"],
            # h00a = seen00, last 0; h00b = seen00, last 1 (still need 11).
            ["h00a", "0", "h00a"], ["h00a", "1", "h00b"],
            ["h00b", "0", "h00a"], ["h00b", "1", "both"],
            # h11a = seen11, last 1; h11b = seen11, last 0 (still need 00).
            ["h11a", "1", "h11a"], ["h11a", "0", "h11b"],
            ["h11b", "1", "h11a"], ["h11b", "0", "both"],
            # both = seen00 AND seen11: accept forever.
            ["both", "0", "both"], ["both", "1", "both"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Minimal DFA (8 states): two sticky latches seen00/seen11 "
                   "with last-symbol memory; 'both' is the only accepting state.",
    },

    # Even #0's AND ends in 1: 4-state product (zeros mod 2, last was 1?).
    "dfa_even_zeros_end_1": {
        "states": [
            {"name": "qE0", "x": 0.18, "y": 0.30, "start": True,  "accept": False},
            {"name": "qE1", "x": 0.60, "y": 0.30, "start": False, "accept": True},
            {"name": "qO0", "x": 0.18, "y": 0.72, "start": False, "accept": False},
            {"name": "qO1", "x": 0.60, "y": 0.72, "start": False, "accept": False},
        ],
        "transitions": [
            ["qE0", "0", "qO0"], ["qE0", "1", "qE1"],
            ["qE1", "0", "qO0"], ["qE1", "1", "qE1"],
            ["qO0", "0", "qE0"], ["qO0", "1", "qO1"],
            ["qO1", "0", "qE0"], ["qO1", "1", "qO1"],
        ],
        "alphabet": ["0", "1"],
        "caption": "State = (#0 parity, last symbol was 1?); only qE1 "
                   "(even 0's and ended on 1) accepts.",
    },

    # Binary value divisible by 3 (MSB first): 3-state residue DFA.
    "dfa_div3_value": {
        "states": [
            {"name": "r0", "x": 0.16, "y": 0.50, "start": True,  "accept": True},
            {"name": "r1", "x": 0.50, "y": 0.28, "start": False, "accept": False},
            {"name": "r2", "x": 0.84, "y": 0.65, "start": False, "accept": False},
        ],
        "transitions": [
            ["r0", "0", "r0"], ["r0", "1", "r1"],
            ["r1", "0", "r2"], ["r1", "1", "r0"],
            ["r2", "0", "r1"], ["r2", "1", "r2"],
        ],
        "alphabet": ["0", "1"],
        "caption": "One state per value mod 3; new=(2·old+bit) mod 3, and the "
                   "accepting start r0 means ε/0 is value 0.",
    },

    # All ones (no zeros): 2-state DFA with a dead sink.
    "dfa_all_ones": {
        "states": [
            {"name": "qOK",   "x": 0.22, "y": 0.40, "start": True,  "accept": True},
            {"name": "qDead", "x": 0.74, "y": 0.60, "start": False, "accept": False},
        ],
        "transitions": [
            ["qOK", "1", "qOK"], ["qOK", "0", "qDead"],
            ["qDead", "0", "qDead"], ["qDead", "1", "qDead"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Stay in accepting qOK while reading 1's; the first 0 traps "
                   "the machine in the dead state.",
    },

    # ================================================================== #
    # chapter: nfa
    # ================================================================== #

    # Contains 101 OR contains 11: looping start + two guess-branches.
    "nfa_contains_101_or_11": {
        "states": [
            {"name": "S",      "x": 0.12, "y": 0.50, "start": True,  "accept": False},
            {"name": "a1",     "x": 0.34, "y": 0.22, "start": False, "accept": False},
            {"name": "a2",     "x": 0.56, "y": 0.22, "start": False, "accept": False},
            {"name": "ACC101", "x": 0.84, "y": 0.30, "start": False, "accept": True},
            {"name": "b1",     "x": 0.34, "y": 0.78, "start": False, "accept": False},
            {"name": "ACC11",  "x": 0.84, "y": 0.70, "start": False, "accept": True},
        ],
        "transitions": [
            ["S", "0", "S"], ["S", "1", "S"],
            ["S", "1", "a1"], ["a1", "0", "a2"], ["a2", "1", "ACC101"],
            ["S", "1", "b1"], ["b1", "1", "ACC11"],
            ["ACC101", "0", "ACC101"], ["ACC101", "1", "ACC101"],
            ["ACC11", "0", "ACC11"], ["ACC11", "1", "ACC11"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Looping start guesses where each pattern begins; one branch "
                   "spells 101, the other 11, both ending in accepting sinks.",
    },

    # Third symbol from the end is 1: classic 4-state NFA.
    "nfa_third_from_end_1": {
        "states": [
            {"name": "q0", "x": 0.14, "y": 0.50, "start": True,  "accept": False},
            {"name": "q1", "x": 0.38, "y": 0.50, "start": False, "accept": False},
            {"name": "q2", "x": 0.62, "y": 0.50, "start": False, "accept": False},
            {"name": "q3", "x": 0.86, "y": 0.50, "start": False, "accept": True},
        ],
        "transitions": [
            ["q0", "0", "q0"], ["q0", "1", "q0"],
            ["q0", "1", "q1"],
            ["q1", "0", "q2"], ["q1", "1", "q2"],
            ["q2", "0", "q3"], ["q2", "1", "q3"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Loop while scanning, then guess a 1 is third-from-last and "
                   "read exactly two more symbols into q3.",
    },

    # Ends with 010: 4-state NFA.
    "nfa_ends_010": {
        "states": [
            {"name": "q0", "x": 0.14, "y": 0.50, "start": True,  "accept": False},
            {"name": "q1", "x": 0.38, "y": 0.50, "start": False, "accept": False},
            {"name": "q2", "x": 0.62, "y": 0.50, "start": False, "accept": False},
            {"name": "q3", "x": 0.86, "y": 0.50, "start": False, "accept": True},
        ],
        "transitions": [
            ["q0", "0", "q0"], ["q0", "1", "q0"],
            ["q0", "0", "q1"], ["q1", "1", "q2"], ["q2", "0", "q3"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Loop at q0, then guess the final 010 begins and spell it to "
                   "the end; q3 accepts only at end of input.",
    },

    # Contains substring 01: 3-state NFA.
    "nfa_contains_01": {
        "states": [
            {"name": "S",   "x": 0.16, "y": 0.50, "start": True,  "accept": False},
            {"name": "q1",  "x": 0.50, "y": 0.50, "start": False, "accept": False},
            {"name": "ACC", "x": 0.84, "y": 0.50, "start": False, "accept": True},
        ],
        "transitions": [
            ["S", "0", "S"], ["S", "1", "S"],
            ["S", "0", "q1"], ["q1", "1", "ACC"],
            ["ACC", "0", "ACC"], ["ACC", "1", "ACC"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Guess where 01 starts (S→q1 on 0, q1→ACC on 1); the "
                   "accepting sink absorbs the rest.",
    },

    # Ends with 11 OR ends with 00: looping start + two length-2 chains.
    "nfa_end_11_or_00": {
        "states": [
            {"name": "S",  "x": 0.14, "y": 0.50, "start": True,  "accept": False},
            {"name": "p1", "x": 0.45, "y": 0.26, "start": False, "accept": False},
            {"name": "P",  "x": 0.80, "y": 0.26, "start": False, "accept": True},
            {"name": "q1", "x": 0.45, "y": 0.74, "start": False, "accept": False},
            {"name": "Q",  "x": 0.80, "y": 0.74, "start": False, "accept": True},
        ],
        "transitions": [
            ["S", "0", "S"], ["S", "1", "S"],
            ["S", "1", "p1"], ["p1", "1", "P"],
            ["S", "0", "q1"], ["q1", "0", "Q"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Two guess-branches: one spells a final 11 (→P), the other "
                   "a final 00 (→Q); a wrong guess dies short of the end.",
    },

    # ================================================================== #
    # chapter: epsilon
    # ================================================================== #

    # All 0's OR all 1's (ε-union): fresh start ε-branches into 0* and 1*.
    "eps_or_allsame": {
        "states": [
            {"name": "S", "x": 0.16, "y": 0.50, "start": True,  "accept": True},
            {"name": "A", "x": 0.62, "y": 0.28, "start": False, "accept": True},
            {"name": "B", "x": 0.62, "y": 0.72, "start": False, "accept": True},
        ],
        "transitions": [
            ["S", EPSILON, "A"], ["S", EPSILON, "B"],
            ["A", "0", "A"],
            ["B", "1", "B"],
        ],
        "alphabet": ["0", "1"],
        "caption": "ε-edges fork into a 0-loop (A) and a 1-loop (B); the empty "
                   "string stays in the ε-closure {S,A,B} and accepts.",
    },

    # 0*1* glued with ε.
    "eps_zeros_then_ones": {
        "states": [
            {"name": "A", "x": 0.28, "y": 0.45, "start": True,  "accept": True},
            {"name": "B", "x": 0.72, "y": 0.55, "start": False, "accept": True},
        ],
        "transitions": [
            ["A", "0", "A"],
            ["A", EPSILON, "B"],
            ["B", "1", "B"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Eat 0's at A, take the one-way ε-hop to B, then eat 1's; "
                   "after the hop no 0 can appear, so no '10' ever occurs.",
    },

    # (01)* with an ε back-edge.
    "eps_01_star": {
        "states": [
            {"name": "S",  "x": 0.18, "y": 0.45, "start": True,  "accept": True},
            {"name": "q1", "x": 0.52, "y": 0.30, "start": False, "accept": False},
            {"name": "q2", "x": 0.80, "y": 0.60, "start": False, "accept": False},
        ],
        "transitions": [
            ["S", "0", "q1"],
            ["q1", "1", "q2"],
            ["q2", EPSILON, "S"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Read one 01 block then take the ε back-edge to S; only S "
                   "accepts, so input must end on a complete block.",
    },

    # 0*1*0* chained by ε.
    "eps_blocks_0_1_0": {
        "states": [
            {"name": "A", "x": 0.18, "y": 0.50, "start": True,  "accept": True},
            {"name": "B", "x": 0.50, "y": 0.35, "start": False, "accept": True},
            {"name": "C", "x": 0.82, "y": 0.55, "start": False, "accept": True},
        ],
        "transitions": [
            ["A", "0", "A"], ["A", EPSILON, "B"],
            ["B", "1", "B"], ["B", EPSILON, "C"],
            ["C", "0", "C"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Three self-loops (0's, 1's, 0's) chained by one-way ε-edges "
                   "fix the order; every state accepts so any block may be empty.",
    },

    # ================================================================== #
    # chapter: convert  (examples are the correct TARGET automaton)
    # ================================================================== #

    # Convert NFA (contains a 1) -> DFA: subset construction, 2 states.
    "conv_nfa_contains_1": {
        "states": [
            {"name": "dA", "x": 0.22, "y": 0.50, "start": True,  "accept": False},
            {"name": "dB", "x": 0.74, "y": 0.50, "start": False, "accept": True},
        ],
        "transitions": [
            ["dA", "0", "dA"], ["dA", "1", "dB"],
            ["dB", "0", "dB"], ["dB", "1", "dB"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Subset DFA: dA={A}, dB={B}; the first 1 moves to the "
                   "accepting dB and stays there.",
    },

    # Convert ε-NFA (0* or 1*) -> DFA: 4 states incl. a dead subset.
    "conv_nfa_eps_allsame": {
        "states": [
            {"name": "d0",   "x": 0.16, "y": 0.50, "start": True,  "accept": True},
            {"name": "dA",   "x": 0.52, "y": 0.26, "start": False, "accept": True},
            {"name": "dB",   "x": 0.52, "y": 0.74, "start": False, "accept": True},
            {"name": "dead", "x": 0.86, "y": 0.50, "start": False, "accept": False},
        ],
        "transitions": [
            ["d0", "0", "dA"], ["d0", "1", "dB"],
            ["dA", "0", "dA"], ["dA", "1", "dead"],
            ["dB", "1", "dB"], ["dB", "0", "dead"],
            ["dead", "0", "dead"], ["dead", "1", "dead"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Start d0=ε-closure{S,A,B}; committing to 0's (dA) or 1's "
                   "(dB) accepts, and any mix falls into the dead subset.",
    },

    # Convert regex (0|1)*1 -> NFA: ends with 1, 2-state NFA.
    "conv_regex_to_nfa_ends1": {
        "states": [
            {"name": "q0", "x": 0.26, "y": 0.50, "start": True,  "accept": False},
            {"name": "q1", "x": 0.74, "y": 0.50, "start": False, "accept": True},
        ],
        "transitions": [
            ["q0", "0", "q0"], ["q0", "1", "q0"],
            ["q0", "1", "q1"],
        ],
        "alphabet": ["0", "1"],
        "caption": "The star becomes the self-loop at q0; the trailing literal "
                   "1 guesses the final symbol into accepting q1.",
    },

    # Convert NFA (ends with 1) -> DFA: 2 subsets.
    "conv_nfa_ends_1": {
        "states": [
            {"name": "dA",  "x": 0.24, "y": 0.50, "start": True,  "accept": False},
            {"name": "dAB", "x": 0.76, "y": 0.50, "start": False, "accept": True},
        ],
        "transitions": [
            ["dA", "0", "dA"], ["dA", "1", "dAB"],
            ["dAB", "0", "dA"], ["dAB", "1", "dAB"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Subsets {A} and {A,B}; {A,B} (accepting) means the last "
                   "symbol read was 1.",
    },

    # Convert NFA (contains 01) -> DFA: 3 subsets.
    "conv_nfa_contains_01": {
        "states": [
            {"name": "dA",  "x": 0.16, "y": 0.50, "start": True,  "accept": False},
            {"name": "dAB", "x": 0.50, "y": 0.50, "start": False, "accept": False},
            {"name": "dC",  "x": 0.84, "y": 0.50, "start": False, "accept": True},
        ],
        "transitions": [
            ["dA", "0", "dAB"], ["dA", "1", "dA"],
            ["dAB", "0", "dAB"], ["dAB", "1", "dC"],
            ["dC", "0", "dC"], ["dC", "1", "dC"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Subsets {A},{A,B},{A,C}; once a 0 then a 1 appear you reach "
                   "the accepting {A,C} and stay.",
    },

    # Convert regex 0* -> NFA: 1-state loop.
    "conv_regex_to_nfa_0star": {
        "states": [
            {"name": "q0", "x": 0.50, "y": 0.50, "start": True, "accept": True},
        ],
        "transitions": [
            ["q0", "0", "q0"],
        ],
        "alphabet": ["0", "1"],
        "caption": "A single accepting state loops on 0; ε is accepted and any "
                   "1 (no edge) kills the run.",
    },

    # Convert regex 01* -> NFA: 2 states.
    "conv_regex_to_nfa_01star": {
        "states": [
            {"name": "q0", "x": 0.28, "y": 0.50, "start": True,  "accept": False},
            {"name": "q1", "x": 0.74, "y": 0.50, "start": False, "accept": True},
        ],
        "transitions": [
            ["q0", "0", "q1"],
            ["q1", "1", "q1"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Literal 0 advances to q1, then the 1* self-loop; q0 is "
                   "non-accepting so the leading 0 is required.",
    },

    # Convert regex 1(0|1)* -> NFA: starts with 1, 2 states.
    "conv_regex_to_nfa_starts1": {
        "states": [
            {"name": "q0", "x": 0.28, "y": 0.50, "start": True,  "accept": False},
            {"name": "q1", "x": 0.74, "y": 0.50, "start": False, "accept": True},
        ],
        "transitions": [
            ["q0", "1", "q1"],
            ["q1", "0", "q1"], ["q1", "1", "q1"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Only a leading 1 leaves q0; q1 then scans the free (0|1)* "
                   "tail.",
    },

    # Convert regex (0|1)*00 -> NFA: ends with 00, 3 states.
    "conv_regex_to_nfa_ends00": {
        "states": [
            {"name": "q0", "x": 0.16, "y": 0.50, "start": True,  "accept": False},
            {"name": "q1", "x": 0.50, "y": 0.50, "start": False, "accept": False},
            {"name": "q2", "x": 0.84, "y": 0.50, "start": False, "accept": True},
        ],
        "transitions": [
            ["q0", "0", "q0"], ["q0", "1", "q0"],
            ["q0", "0", "q1"], ["q1", "0", "q2"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Scan freely at q0, then guess the final 00 and read two 0's "
                   "into accepting q2.",
    },

    # Convert regex 0*1* -> NFA (uses ε): 2 states + ε-edge.
    "conv_regex_to_nfa_0s1s": {
        "states": [
            {"name": "q0", "x": 0.28, "y": 0.45, "start": True,  "accept": False},
            {"name": "q1", "x": 0.72, "y": 0.55, "start": False, "accept": True},
        ],
        "transitions": [
            ["q0", "0", "q0"],
            ["q0", EPSILON, "q1"],
            ["q1", "1", "q1"],
        ],
        "alphabet": ["0", "1"],
        "caption": "0* loop at q0, a free ε-hop to q1, then the 1* loop; the "
                   "ε-move makes ε and all-0/all-1 strings accept.",
    },

    # Convert regex (01)* -> NFA: 2 states, back-edge on 1.
    "conv_regex_to_nfa_01star_loop": {
        "states": [
            {"name": "q0", "x": 0.30, "y": 0.45, "start": True,  "accept": True},
            {"name": "q1", "x": 0.72, "y": 0.55, "start": False, "accept": False},
        ],
        "transitions": [
            ["q0", "0", "q1"],
            ["q1", "1", "q0"],
        ],
        "alphabet": ["0", "1"],
        "caption": "q0→q1 on 0, q1→q0 on 1 completes one '01'; accepting q0 "
                   "gives ε and only whole blocks.",
    },

    # Convert NFA (contains 11) -> DFA: 3 subsets.
    "conv_nfa_contains_11": {
        "states": [
            {"name": "dA",  "x": 0.16, "y": 0.50, "start": True,  "accept": False},
            {"name": "dAB", "x": 0.50, "y": 0.50, "start": False, "accept": False},
            {"name": "dAC", "x": 0.84, "y": 0.50, "start": False, "accept": True},
        ],
        "transitions": [
            ["dA", "0", "dA"], ["dA", "1", "dAB"],
            ["dAB", "0", "dA"], ["dAB", "1", "dAC"],
            ["dAC", "0", "dAC"], ["dAC", "1", "dAC"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Subsets {A},{A,B},{A,C}; a 1 then another 1 reaches the "
                   "accepting {A,C} and it loops forever.",
    },

    # Convert NFA (ends with 0) -> DFA: 2 subsets.
    "conv_nfa_ends_0": {
        "states": [
            {"name": "dA",  "x": 0.24, "y": 0.50, "start": True,  "accept": False},
            {"name": "dAB", "x": 0.76, "y": 0.50, "start": False, "accept": True},
        ],
        "transitions": [
            ["dA", "0", "dAB"], ["dA", "1", "dA"],
            ["dAB", "0", "dAB"], ["dAB", "1", "dA"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Subsets {A} and {A,B}; {A,B} (accepting) means the last "
                   "symbol read was 0.",
    },

    # ================================================================== #
    # chapter: regex  (examples are small DFAs/NFAs recognizing the language)
    # ================================================================== #

    # Starts with 10: 10(0|1)*.
    "re_starts_10": {
        "states": [
            {"name": "q0", "x": 0.14, "y": 0.50, "start": True,  "accept": False},
            {"name": "q1", "x": 0.42, "y": 0.35, "start": False, "accept": False},
            {"name": "q2", "x": 0.72, "y": 0.35, "start": False, "accept": True},
            {"name": "dead", "x": 0.50, "y": 0.80, "start": False, "accept": False},
        ],
        "transitions": [
            ["q0", "1", "q1"], ["q0", "0", "dead"],
            ["q1", "0", "q2"], ["q1", "1", "dead"],
            ["q2", "0", "q2"], ["q2", "1", "q2"],
            ["dead", "0", "dead"], ["dead", "1", "dead"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Force the literal 1 then 0; after reaching accepting q2 the "
                   "tail is free. Any other start falls dead.",
    },

    # Ends with 10: (0|1)*10, done as a DFA tracking the trailing match.
    "re_ends_10": {
        "states": [
            {"name": "A", "x": 0.18, "y": 0.50, "start": True,  "accept": False},
            {"name": "B", "x": 0.50, "y": 0.30, "start": False, "accept": False},
            {"name": "C", "x": 0.82, "y": 0.55, "start": False, "accept": True},
        ],
        "transitions": [
            ["A", "1", "B"], ["A", "0", "A"],
            ["B", "0", "C"], ["B", "1", "B"],
            ["C", "1", "B"], ["C", "0", "A"],
        ],
        "alphabet": ["0", "1"],
        "caption": "DFA tracking the trailing match of 10: B = 'last was 1', "
                   "C = 'just saw 10' (accept).",
    },

    # Contains 10: (0|1)*10(0|1)* as a DFA.
    "re_contains_10": {
        "states": [
            {"name": "A", "x": 0.18, "y": 0.50, "start": True,  "accept": False},
            {"name": "B", "x": 0.50, "y": 0.30, "start": False, "accept": False},
            {"name": "C", "x": 0.82, "y": 0.55, "start": False, "accept": True},
        ],
        "transitions": [
            ["A", "1", "B"], ["A", "0", "A"],
            ["B", "0", "C"], ["B", "1", "B"],
            ["C", "0", "C"], ["C", "1", "C"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Wait for a 1 (B), then a following 0 locks into the "
                   "accepting sink C: the substring 10 has appeared.",
    },

    # Does NOT contain 10: 0*1* DFA with a dead state.
    "re_no_10": {
        "states": [
            {"name": "Z", "x": 0.20, "y": 0.40, "start": True,  "accept": True},
            {"name": "O", "x": 0.56, "y": 0.40, "start": False, "accept": True},
            {"name": "dead", "x": 0.80, "y": 0.75, "start": False, "accept": False},
        ],
        "transitions": [
            ["Z", "0", "Z"], ["Z", "1", "O"],
            ["O", "1", "O"], ["O", "0", "dead"],
            ["dead", "0", "dead"], ["dead", "1", "dead"],
        ],
        "alphabet": ["0", "1"],
        "caption": "0's then 1's (0*1*): once you read a 1 you may only read "
                   "1's; a later 0 (the '10') falls into the dead state.",
    },

    # 2nd-to-last bit is 1: (0|1)*1(0|1). Minimal 4-state DFA tracking the
    # last two bits; accept when the earlier of those two bits is a 1.
    "re_second_last_1": {
        "states": [
            {"name": "s",   "x": 0.14, "y": 0.50, "start": True,  "accept": False},
            {"name": "p1",  "x": 0.40, "y": 0.50, "start": False, "accept": False},
            {"name": "a10", "x": 0.72, "y": 0.28, "start": False, "accept": True},
            {"name": "a11", "x": 0.72, "y": 0.72, "start": False, "accept": True},
        ],
        "transitions": [
            # s: last bit 0 (or empty) and second-to-last is not 1.
            ["s", "0", "s"], ["s", "1", "p1"],
            # p1: last bit is 1, second-to-last not yet 1.
            ["p1", "0", "a10"], ["p1", "1", "a11"],
            # a10: ends '10' => second-to-last is 1 (accept); last bit now 0.
            ["a10", "0", "s"], ["a10", "1", "p1"],
            # a11: ends '11' => second-to-last is 1 (accept); last bit now 1.
            ["a11", "0", "a10"], ["a11", "1", "a11"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Remember the last two bits; a10 ('...10') and a11 ('...11') "
                   "accept because their second-to-last bit is 1.",
    },

    # Exactly three 1's: 0*10*10*10* as a DFA with a dead overflow state.
    "re_exactly_three_1": {
        "states": [
            {"name": "n0", "x": 0.12, "y": 0.50, "start": True,  "accept": False},
            {"name": "n1", "x": 0.33, "y": 0.50, "start": False, "accept": False},
            {"name": "n2", "x": 0.54, "y": 0.50, "start": False, "accept": False},
            {"name": "n3", "x": 0.75, "y": 0.35, "start": False, "accept": True},
            {"name": "n4", "x": 0.75, "y": 0.78, "start": False, "accept": False},
        ],
        "transitions": [
            ["n0", "0", "n0"], ["n0", "1", "n1"],
            ["n1", "0", "n1"], ["n1", "1", "n2"],
            ["n2", "0", "n2"], ["n2", "1", "n3"],
            ["n3", "0", "n3"], ["n3", "1", "n4"],
            ["n4", "0", "n4"], ["n4", "1", "n4"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Count 1's; n3 (exactly three) accepts, 0's self-loop, and a "
                   "fourth 1 falls into the dead n4.",
    },

    # At least two 1's: 0*10*1(0|1)*.
    "re_at_least_two_1": {
        "states": [
            {"name": "z0", "x": 0.18, "y": 0.50, "start": True,  "accept": False},
            {"name": "z1", "x": 0.50, "y": 0.50, "start": False, "accept": False},
            {"name": "z2", "x": 0.82, "y": 0.50, "start": False, "accept": True},
        ],
        "transitions": [
            ["z0", "0", "z0"], ["z0", "1", "z1"],
            ["z1", "0", "z1"], ["z1", "1", "z2"],
            ["z2", "0", "z2"], ["z2", "1", "z2"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Count 1's up to two; the second 1 locks into accepting z2 "
                   "and everything after is free.",
    },

    # Even length: ((0|1)(0|1))*.
    "re_even_length": {
        "states": [
            {"name": "even", "x": 0.28, "y": 0.45, "start": True,  "accept": True},
            {"name": "odd",  "x": 0.72, "y": 0.55, "start": False, "accept": False},
        ],
        "transitions": [
            ["even", "0", "odd"], ["even", "1", "odd"],
            ["odd", "0", "even"], ["odd", "1", "even"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Toggle parity on every symbol; the accepting 'even' state "
                   "includes the empty string.",
    },

    # Even number of 1's: 0*(10*10*)*.
    "re_even_ones": {
        "states": [
            {"name": "even", "x": 0.28, "y": 0.45, "start": True,  "accept": True},
            {"name": "odd",  "x": 0.72, "y": 0.55, "start": False, "accept": False},
        ],
        "transitions": [
            ["even", "0", "even"], ["even", "1", "odd"],
            ["odd", "0", "odd"], ["odd", "1", "even"],
        ],
        "alphabet": ["0", "1"],
        "caption": "0's self-loop (they don't change parity); each 1 flips "
                   "between even (accept) and odd.",
    },

    # Length at least 3: (0|1)(0|1)(0|1)(0|1)*.
    "re_length_ge_3": {
        "states": [
            {"name": "L0", "x": 0.14, "y": 0.50, "start": True,  "accept": False},
            {"name": "L1", "x": 0.38, "y": 0.50, "start": False, "accept": False},
            {"name": "L2", "x": 0.62, "y": 0.50, "start": False, "accept": False},
            {"name": "L3", "x": 0.86, "y": 0.50, "start": False, "accept": True},
        ],
        "transitions": [
            ["L0", "0", "L1"], ["L0", "1", "L1"],
            ["L1", "0", "L2"], ["L1", "1", "L2"],
            ["L2", "0", "L3"], ["L2", "1", "L3"],
            ["L3", "0", "L3"], ["L3", "1", "L3"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Count length; after three symbols you reach accepting L3 "
                   "and stay there.",
    },

    # Only the empty string: ε.
    "re_only_epsilon": {
        "states": [
            {"name": "q0",   "x": 0.26, "y": 0.45, "start": True,  "accept": True},
            {"name": "dead", "x": 0.72, "y": 0.55, "start": False, "accept": False},
        ],
        "transitions": [
            ["q0", "0", "dead"], ["q0", "1", "dead"],
            ["dead", "0", "dead"], ["dead", "1", "dead"],
        ],
        "alphabet": ["0", "1"],
        "caption": "The start accepts ε; any symbol at all leaves for the dead "
                   "state, so only the empty string is accepted.",
    },

    # Contains 000: (0|1)*000(0|1)* as a DFA on the trailing 0-run.
    "re_contains_000": {
        "states": [
            {"name": "z0", "x": 0.14, "y": 0.50, "start": True,  "accept": False},
            {"name": "z1", "x": 0.37, "y": 0.50, "start": False, "accept": False},
            {"name": "z2", "x": 0.60, "y": 0.50, "start": False, "accept": False},
            {"name": "z3", "x": 0.86, "y": 0.50, "start": False, "accept": True},
        ],
        "transitions": [
            ["z0", "0", "z1"], ["z0", "1", "z0"],
            ["z1", "0", "z2"], ["z1", "1", "z0"],
            ["z2", "0", "z3"], ["z2", "1", "z0"],
            ["z3", "0", "z3"], ["z3", "1", "z3"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Count the current run of 0's; three in a row reaches the "
                   "accepting sink z3 (000 found).",
    },

    # Starts with 0: 0(0|1)*.
    "re_starts_0": {
        "states": [
            {"name": "q0",   "x": 0.18, "y": 0.45, "start": True,  "accept": False},
            {"name": "q1",   "x": 0.56, "y": 0.35, "start": False, "accept": True},
            {"name": "dead", "x": 0.56, "y": 0.78, "start": False, "accept": False},
        ],
        "transitions": [
            ["q0", "0", "q1"], ["q0", "1", "dead"],
            ["q1", "0", "q1"], ["q1", "1", "q1"],
            ["dead", "0", "dead"], ["dead", "1", "dead"],
        ],
        "alphabet": ["0", "1"],
        "caption": "A leading 0 reaches accepting q1 (then anything); a leading "
                   "1 falls dead.",
    },

    # Contains 11: (0|1)*11(0|1)* as a DFA on the trailing 1-run.
    "re_contains_11": {
        "states": [
            {"name": "o0", "x": 0.18, "y": 0.50, "start": True,  "accept": False},
            {"name": "o1", "x": 0.50, "y": 0.30, "start": False, "accept": False},
            {"name": "o2", "x": 0.82, "y": 0.55, "start": False, "accept": True},
        ],
        "transitions": [
            ["o0", "1", "o1"], ["o0", "0", "o0"],
            ["o1", "1", "o2"], ["o1", "0", "o0"],
            ["o2", "0", "o2"], ["o2", "1", "o2"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Track the current run of 1's; two in a row locks into the "
                   "accepting sink o2 (11 found).",
    },

    # Length exactly 3: (0|1)(0|1)(0|1).
    "re_len_exactly_3": {
        "states": [
            {"name": "L0", "x": 0.12, "y": 0.50, "start": True,  "accept": False},
            {"name": "L1", "x": 0.33, "y": 0.50, "start": False, "accept": False},
            {"name": "L2", "x": 0.54, "y": 0.50, "start": False, "accept": False},
            {"name": "L3", "x": 0.75, "y": 0.33, "start": False, "accept": True},
            {"name": "L4", "x": 0.75, "y": 0.78, "start": False, "accept": False},
        ],
        "transitions": [
            ["L0", "0", "L1"], ["L0", "1", "L1"],
            ["L1", "0", "L2"], ["L1", "1", "L2"],
            ["L2", "0", "L3"], ["L2", "1", "L3"],
            ["L3", "0", "L4"], ["L3", "1", "L4"],
            ["L4", "0", "L4"], ["L4", "1", "L4"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Count length; only L3 (exactly three symbols) accepts, a "
                   "fourth symbol falls into the dead L4.",
    },

    # Starts with 1 and ends with 0: 1(0|1)*0.
    "re_start1_end0": {
        "states": [
            {"name": "q0",   "x": 0.14, "y": 0.45, "start": True,  "accept": False},
            {"name": "q1",   "x": 0.44, "y": 0.30, "start": False, "accept": False},
            {"name": "q2",   "x": 0.74, "y": 0.30, "start": False, "accept": True},
            {"name": "dead", "x": 0.44, "y": 0.80, "start": False, "accept": False},
        ],
        "transitions": [
            ["q0", "1", "q1"], ["q0", "0", "dead"],
            ["q1", "0", "q2"], ["q1", "1", "q1"],
            ["q2", "1", "q1"], ["q2", "0", "q2"],
            ["dead", "0", "dead"], ["dead", "1", "dead"],
        ],
        "alphabet": ["0", "1"],
        "caption": "Require a leading 1 (q0→q1); q2 marks 'last symbol was 0' "
                   "and accepts. A leading 0 falls dead.",
    },

    # Does NOT contain 00: (1|01)*(0|ε). DFA with dead state.
    "re_no_00": {
        "states": [
            {"name": "A",    "x": 0.20, "y": 0.40, "start": True,  "accept": True},
            {"name": "B",    "x": 0.56, "y": 0.40, "start": False, "accept": True},
            {"name": "dead", "x": 0.80, "y": 0.75, "start": False, "accept": False},
        ],
        "transitions": [
            # A = last symbol was 1 or string empty (no pending 0).
            ["A", "1", "A"], ["A", "0", "B"],
            # B = last symbol was 0 (a second 0 now would make 00).
            ["B", "1", "A"], ["B", "0", "dead"],
            ["dead", "0", "dead"], ["dead", "1", "dead"],
        ],
        "alphabet": ["0", "1"],
        "caption": "B means 'last symbol was 0'; a second 0 (the '00') falls "
                   "into the dead state. Both A and B accept.",
    },
}


# ---------------------------------------------------------------------- #
# Building and verification
# ---------------------------------------------------------------------- #
def build_automaton(spec: Spec) -> Automaton:
    """Construct an :class:`Automaton` from an ``EXAMPLE_SPECS`` spec dict.

    States are added with their canvas-fraction coordinates and start/accept
    flags; transitions are added in order. ``"ε"`` (``automaton.EPSILON``) is a
    valid transition symbol for NFA examples.

    Args:
        spec: A dict with ``states``, ``transitions`` and ``alphabet`` as
            documented at module level.

    Returns:
        A ready-to-simulate :class:`Automaton`.
    """
    aut = Automaton()
    states: List[Dict[str, object]] = spec["states"]        # type: ignore[assignment]
    for st in states:
        aut.add_state(
            name=str(st["name"]),
            x=float(st["x"]),
            y=float(st["y"]),
            is_start=bool(st.get("start", False)),
            is_accept=bool(st.get("accept", False)),
        )
    # Make sure every alphabet symbol is registered even if unused by an edge.
    for sym in spec.get("alphabet", []):            # type: ignore[union-attr]
        aut.alphabet.add(str(sym))
    transitions: List[List[str]] = spec["transitions"]      # type: ignore[assignment]
    for src, sym, dst in transitions:
        aut.add_transition(src, sym, dst)
    return aut


def _binary_words(max_len: int) -> List[str]:
    """Every binary string of length 0..max_len (ε first)."""
    words = [""]
    for n in range(1, max_len + 1):
        for tup in product("01", repeat=n):
            words.append("".join(tup))
    return words


def verify_example(problem: Problem, spec: Spec,
                   max_len: int = 8) -> Tuple[bool, str]:
    """Check that ``spec`` recognizes EXACTLY ``problem``'s language.

    Builds the spec's automaton and simulates it on every binary string up to
    length ``max_len``, comparing the accept/reject verdict against
    ``problem.membership``.

    Args:
        problem: The problem whose language the example should match.
        spec: The example spec to verify.
        max_len: Longest word length to test (inclusive).

    Returns:
        ``(True, message)`` if the languages agree on all tested words, else
        ``(False, message)`` where the message reports the first counterexample.
    """
    aut = build_automaton(spec)
    for w in _binary_words(max_len):
        sim = aut.simulate(w)
        got = False if sim.error else sim.accepted
        expected = problem.membership(w)
        if got != expected:
            disp = w if w else "ε (empty string)"
            return (
                False,
                f"Mismatch on \"{disp}\": example "
                f"{'accepts' if got else 'rejects'} but the language "
                f"{'accepts' if expected else 'rejects'}.",
            )
    return (True, f"OK: language-equivalent on all binary words up to "
                  f"length {max_len}.")


# ---------------------------------------------------------------------- #
# Public lookup API
# ---------------------------------------------------------------------- #
def has_example(key: str) -> bool:
    """Return True if a drawable example exists for the given problem key."""
    return key in EXAMPLE_SPECS


def get_example(key: str) -> Optional[Spec]:
    """Return the example spec for ``key``, or ``None`` if there is none."""
    return EXAMPLE_SPECS.get(key)
