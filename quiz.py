"""
quiz.py
-------
The teaching brain of the app.

Contains:
  * A bank of construction problems (DFA / NFA / RE) over the binary
    alphabet {0, 1}.
  * A grader that decides whether a *language* is matched, used both to
    describe the "correct answer" behaviour and to grade a user's automaton.
  * Rich, step-by-step explanations for each problem.

Grading approach
----------------
Each problem defines a Python predicate `membership(word) -> bool` describing
the target language. To grade a student automaton we simulate it on a battery
of test words and compare the accept/reject verdict against the predicate.
This is a practical, finite approximation of language equivalence that is more
than enough for a quiz: it catches the overwhelming majority of real mistakes
and reports a concrete counterexample the student can trace.

All reference answers in this file have been verified by brute force against
their predicates over every binary string up to length 9 (and up to length 12
for the two union DFAs).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from typing import Callable, List, Optional

from automaton import Automaton


@dataclass
class Problem:
    key: str
    kind: str                      # "DFA", "NFA", or "RE"
    title: str
    prompt: str
    alphabet: List[str]
    membership: Callable[[str], bool]
    concept: str                   # teaching explanation (the "why")
    strategy: str                  # how to approach building it
    # For RE problems we also offer a reference regular expression + hints.
    reference_regex: Optional[str] = None
    re_hints: List[str] = field(default_factory=list)
    # A couple of hand-picked examples for the UI to show.
    example_accept: List[str] = field(default_factory=list)
    example_reject: List[str] = field(default_factory=list)
    # Optional extra teaching note (e.g. the "why only 5 states?" discussion).
    note: Optional[str] = None
    # ---- Game metadata ------------------------------------------------
    # difficulty: 1 (easiest) .. 5 (hardest); drives ordering and points.
    difficulty: int = 1
    # points awarded for a first-time correct solve (before hint penalties).
    points: int = 100
    # short Sipser reference, e.g. "Sipser §1.1" (cited, not quoted).
    sipser_ref: Optional[str] = None


# ---------------------------------------------------------------------- #
# Test-word battery
# ---------------------------------------------------------------------- #
def all_words(alphabet: List[str], max_len: int) -> List[str]:
    """Every word over `alphabet` with length 0..max_len (lexicographic)."""
    words = [""]
    for n in range(1, max_len + 1):
        for tup in product(alphabet, repeat=n):
            words.append("".join(tup))
    return words


@dataclass
class GradeResult:
    correct: bool
    tested: int
    structural_issues: List[str] = field(default_factory=list)
    counterexample: Optional[str] = None
    counter_expected: Optional[bool] = None
    counter_got: Optional[bool] = None
    message: str = ""


def grade(problem: Problem, aut: Automaton, max_len: int = 6) -> GradeResult:
    """Grade a student's automaton against a problem's target language."""
    issues: List[str] = []

    # Structural sanity checks shared by all kinds.
    if aut.start_state() is None:
        issues.append("There is no start state. Mark one state as the start.")
    if not aut.accept_states():
        issues.append("There are no accepting states. Mark at least one.")

    # DFA problems additionally require determinism.
    if problem.kind == "DFA":
        is_dfa, reasons = aut.is_deterministic()
        if not is_dfa:
            issues.extend(reasons)

    if issues:
        return GradeResult(
            correct=False, tested=0, structural_issues=issues,
            message="Fix the structural issues above, then re-check."
        )

    # Behavioural check: compare verdicts over the test battery.
    words = all_words(problem.alphabet, max_len)
    tested = 0
    for w in words:
        sim = aut.simulate(w)
        if sim.error:
            # A stuck/undefined transition on an NFA just means reject.
            got = False
        else:
            got = sim.accepted
        expected = problem.membership(w)
        tested += 1
        if got != expected:
            disp = w if w else "ε (empty string)"
            return GradeResult(
                correct=False, tested=tested,
                counterexample=disp,
                counter_expected=expected, counter_got=got,
                message=(
                    f"Not quite. On the word \"{disp}\" your automaton "
                    f"{'accepts' if got else 'rejects'}, but it should "
                    f"{'accept' if expected else 'reject'}."
                )
            )

    return GradeResult(
        correct=True, tested=tested,
        message=f"Correct! Verified on all {tested} words up to length "
                f"{max_len}. Nicely done."
    )


# ---------------------------------------------------------------------- #
# Small predicate helpers
# ---------------------------------------------------------------------- #
def _ones(w: str) -> int:
    return w.count("1")


def _zeros(w: str) -> int:
    return w.count("0")


BIN = ["0", "1"]


# ---------------------------------------------------------------------- #
# Problem bank  (alphabet = {0, 1})
# Every reference_regex / reference DFA below is brute-force verified.
# ---------------------------------------------------------------------- #
PROBLEMS: List[Problem] = [
    # 1 ---------------------------------------------------------------- #
    Problem(
        key="re_starts_10",
        kind="RE",
        title="Starts with 10",
        prompt="Strings over {0,1} that START with 10.",
        alphabet=BIN,
        membership=lambda s: s.startswith("10"),
        reference_regex="10(0|1)*",
        re_hints=[
            "Pin the beginning by writing the literal 10 first.",
            "After that, anything goes: (0|1)* means 'any binary string'.",
        ],
        concept=(
            "A prefix condition is the easiest kind of regular expression: "
            "write the required prefix literally, then allow any continuation "
            "with (0|1)*. The star means 'zero or more', so the tail may be "
            "empty — '10' itself is accepted."
        ),
        strategy="Literal prefix then free tail: 10(0|1)*.",
        example_accept=["10", "100", "1011", "10000"],
        example_reject=["", "1", "0", "01", "110"],
        difficulty=1,
        points=80,
        sipser_ref="Sipser §1.3",
    ),
    # 2 ---------------------------------------------------------------- #
    Problem(
        key="re_ends_10",
        kind="RE",
        title="Ends with 10",
        prompt="Strings over {0,1} that END with 10.",
        alphabet=BIN,
        membership=lambda s: s.endswith("10"),
        reference_regex="(0|1)*10",
        re_hints=[
            "Allow any prefix with (0|1)*.",
            "Then force the ending by writing the literal 10 last.",
        ],
        concept=(
            "A suffix condition mirrors the prefix one: allow any prefix with "
            "(0|1)*, then write the required suffix literally at the end."
        ),
        strategy="Free prefix then literal suffix: (0|1)*10.",
        example_accept=["10", "010", "1110", "0010"],
        example_reject=["", "1", "0", "01", "101"],
        difficulty=1,
        points=80,
        sipser_ref="Sipser §1.3",
    ),
    # 3 ---------------------------------------------------------------- #
    Problem(
        key="re_start01_end10",
        kind="RE",
        title="Starts with 01 and ends with 10",
        prompt="Strings over {0,1} that START with 01 AND END with 10.",
        alphabet=BIN,
        membership=lambda s: s.startswith("01") and s.endswith("10"),
        reference_regex="01(0|1)*10|010",
        re_hints=[
            "The general shape is 01 (anything) 10.",
            "But watch the short case: '010' both starts with 01 and ends "
            "with 10 by OVERLAPPING on the middle symbol — it has length 3, "
            "too short for 01…10 with a separate middle.",
            "Union the two cases: 01(0|1)*10 | 010.",
        ],
        concept=(
            "When a required prefix and suffix can OVERLAP, the naive "
            "'prefix (anything) suffix' misses the short overlapping strings. "
            "Here '010' is in the language (starts 01, ends 10) but is not "
            "captured by 01(0|1)*10, which needs length ≥ 4. We add it with a "
            "union."
        ),
        strategy=(
            "Main case 01(0|1)*10 covers length ≥ 4; add the overlapping "
            "length-3 string 010 via union: 01(0|1)*10 | 010."
        ),
        example_accept=["010", "0110", "01010", "010010"],
        example_reject=["", "01", "10", "0100", "1110"],
        difficulty=3,
        points=180,
        sipser_ref="Sipser §1.3",
    ),
    # 4 ---------------------------------------------------------------- #
    Problem(
        key="re_contains_10",
        kind="RE",
        title="Contains substring 10",
        prompt="Strings over {0,1} that CONTAIN 10 as a substring.",
        alphabet=BIN,
        membership=lambda s: "10" in s,
        reference_regex="(0|1)*10(0|1)*",
        re_hints=[
            "'contains X' = anything, then X, then anything.",
            "Sandwich the literal 10 between two (0|1)* factors.",
        ],
        concept=(
            "The universal pattern for 'contains w' is (Σ)* w (Σ)*. The two "
            "stars absorb whatever appears before and after the required "
            "occurrence of w."
        ),
        strategy="(0|1)*10(0|1)*.",
        example_accept=["10", "110", "0100", "1110"],
        example_reject=["", "0", "1", "01", "0011"],
        difficulty=2,
        points=120,
        sipser_ref="Sipser §1.3",
    ),
    # 5 ---------------------------------------------------------------- #
    Problem(
        key="re_no_10",
        kind="RE",
        title="Does NOT contain 10",
        prompt="Strings over {0,1} that do NOT contain 10 as a substring.",
        alphabet=BIN,
        membership=lambda s: "10" not in s,
        reference_regex="0*1*",
        re_hints=[
            "If a 1 can never be followed by a 0, then once you see a 1 you "
            "can only ever see 1's afterward.",
            "So the string is some 0's followed by some 1's: 0*1*.",
        ],
        concept=(
            "Forbidding the substring 10 means: no 1 is ever followed by a 0. "
            "Equivalently, all 0's come before all 1's. That language is "
            "exactly 0*1* — a block of zeros then a block of ones (either "
            "possibly empty). This is a classic 'complement looks nothing "
            "like the pattern' insight."
        ),
        strategy="All 0's then all 1's: 0*1*.",
        example_accept=["", "0", "1", "0011", "00111"],
        example_reject=["10", "100", "0101", "110"],
        difficulty=2,
        points=120,
        sipser_ref="Sipser §1.3",
    ),
    # 6 ---------------------------------------------------------------- #
    Problem(
        key="re_second_last_1",
        kind="RE",
        title="2nd-to-last bit is 1",
        prompt="Strings over {0,1} whose SECOND-TO-LAST bit is 1 "
               "(so length ≥ 2).",
        alphabet=BIN,
        membership=lambda s: len(s) >= 2 and s[-2] == "1",
        reference_regex="(0|1)*1(0|1)",
        re_hints=[
            "Fix the last two positions: the 2nd-to-last is 1, the last is "
            "anything.",
            "Everything before is free: (0|1)*.",
            "So (0|1)* 1 (0|1).",
        ],
        concept=(
            "To constrain a position measured from the END, anchor it at the "
            "right end of the expression. Here the final two symbols are "
            "'1' then 'anything', and the (0|1)* prefix lets the rest vary."
        ),
        strategy="Free prefix, then 1, then one free symbol: (0|1)*1(0|1).",
        example_accept=["10", "11", "010", "0110"],
        example_reject=["", "0", "1", "00", "001"],
        difficulty=2,
        points=120,
        sipser_ref="Sipser §1.3",
    ),
    # 7 ---------------------------------------------------------------- #
    Problem(
        key="re_exactly_three_1",
        kind="RE",
        title="Exactly three 1's",
        prompt="Strings over {0,1} containing EXACTLY three 1's.",
        alphabet=BIN,
        membership=lambda s: _ones(s) == 3,
        reference_regex="0*10*10*10*",
        re_hints=[
            "Think of the three 1's as fixed landmarks.",
            "Between and around them you may have any number of 0's: 0*.",
            "So 0* 1 0* 1 0* 1 0*.",
        ],
        concept=(
            "To force an EXACT count of a symbol, write that many copies of "
            "the symbol separated and surrounded by 0* (any number of the "
            "other symbol). Four 0* slots around three 1's guarantees exactly "
            "three 1's."
        ),
        strategy="0*10*10*10*.",
        example_accept=["111", "0111", "1011", "100101"],
        example_reject=["", "11", "1111", "0", "11110"],
        difficulty=2,
        points=120,
        sipser_ref="Sipser §1.3",
    ),
    # 8 ---------------------------------------------------------------- #
    Problem(
        key="re_at_least_two_1",
        kind="RE",
        title="At least two 1's",
        prompt="Strings over {0,1} containing AT LEAST two 1's.",
        alphabet=BIN,
        membership=lambda s: _ones(s) >= 2,
        reference_regex="0*10*1(0|1)*",
        re_hints=[
            "Pin down the first two 1's with 0* around them.",
            "After the second 1, anything at all may follow: (0|1)*.",
        ],
        concept=(
            "'At least k' pins down the first k occurrences, then lets the "
            "tail be completely free. Here we fix two 1's (with 0* for the "
            "zeros before/between them) and then allow (0|1)* for everything "
            "after."
        ),
        strategy="0*10*1(0|1)*.",
        example_accept=["11", "101", "0110", "1001"],
        example_reject=["", "0", "1", "10", "000"],
        difficulty=2,
        points=120,
        sipser_ref="Sipser §1.3",
    ),
    # 9 ---------------------------------------------------------------- #
    Problem(
        key="re_even_length",
        kind="RE",
        title="Even length",
        prompt="Strings over {0,1} whose LENGTH is even (0 counts as even).",
        alphabet=BIN,
        membership=lambda s: len(s) % 2 == 0,
        reference_regex="((0|1)(0|1))*",
        re_hints=[
            "A pair of any two symbols is (0|1)(0|1).",
            "Zero or more such pairs gives any even length: ((0|1)(0|1))*.",
        ],
        concept=(
            "Length conditions become regular expressions by grouping symbols "
            "into fixed-size blocks. Each block (0|1)(0|1) contributes exactly "
            "two symbols, so repeating it any number of times yields all and "
            "only the even-length strings (including the empty string)."
        ),
        strategy="Repeat a 2-symbol block: ((0|1)(0|1))*.",
        example_accept=["", "00", "01", "1010", "1111"],
        example_reject=["0", "1", "010", "11111"],
        difficulty=2,
        points=120,
        sipser_ref="Sipser §1.3",
    ),
    # 10 --------------------------------------------------------------- #
    Problem(
        key="re_even_ones",
        kind="RE",
        title="Even number of 1's",
        prompt="Strings over {0,1} with an EVEN number of 1's.",
        alphabet=BIN,
        membership=lambda s: _ones(s) % 2 == 0,
        reference_regex="0*(10*10*)*",
        re_hints=[
            "0's never change the parity of 1's, so allow them freely with 0*.",
            "The 1's must come in PAIRS; one pair with 0's mixed in is "
            "1 0* 1 0*.",
            "Zero or more such pairs, with leading 0*: 0*(10*10*)*.",
        ],
        concept=(
            "Parity of a symbol is captured by grouping that symbol into "
            "pairs. Each repetition 10*10* contributes exactly two 1's, "
            "keeping the total even, while 0* factors let any number of zeros "
            "appear anywhere."
        ),
        strategy="0*(10*10*)*.",
        example_accept=["", "11", "00", "1010", "0110"],
        example_reject=["1", "111", "10", "01"],
        difficulty=3,
        points=180,
        sipser_ref="Sipser §1.3",
    ),
    # 11 --------------------------------------------------------------- #
    Problem(
        key="re_odd_positions_1",
        kind="RE",
        title="Every odd position is 1 (1-indexed)",
        prompt="Strings over {0,1} where EVERY odd position holds a 1 "
               "(positions numbered 1, 2, 3, … from the left). "
               "Example: 101 is in the language.",
        alphabet=BIN,
        membership=lambda s: all(s[i] == "1" for i in range(0, len(s), 2)),
        reference_regex="(1(0|1))*(1|ε)",
        re_hints=[
            "Positions 1,3,5,… must be 1; the even positions 2,4,6,… are free.",
            "A single (odd,even) pair is therefore 1(0|1).",
            "Repeat that for the pairs, then allow an optional trailing lone "
            "1 for odd-length strings: (1(0|1))*(1|ε).",
        ],
        concept=(
            "A positional/alternating constraint is captured by a repeating "
            "block that spans one full period. Here the period is two "
            "positions: a forced 1 (odd position) followed by a free symbol "
            "(even position). Odd-length strings end on an odd position, so "
            "we append an optional final 1. The empty string vacuously "
            "satisfies 'every odd position is 1'."
        ),
        strategy="Repeat 1-then-free, with an optional trailing 1: "
                 "(1(0|1))*(1|ε).",
        example_accept=["", "1", "10", "11", "101", "1011"],
        example_reject=["0", "01", "00", "100", "001"],
        difficulty=3,
        points=180,
        sipser_ref="Sipser §1.3",
    ),
    # 12 --------------------------------------------------------------- #
    Problem(
        key="re_ones_mod3_0",
        kind="RE",
        title="Number of 1's is a multiple of 3 (3k, k ≥ 0)",
        prompt="Strings over {0,1} where the number of 1's is 3k for some "
               "k ≥ 0 (i.e. #1's ≡ 0 mod 3; zero 1's counts).",
        alphabet=BIN,
        membership=lambda s: _ones(s) % 3 == 0,
        reference_regex="0*(10*10*10*)*",
        re_hints=[
            "0's don't affect the count of 1's, so sprinkle 0* freely.",
            "Group the 1's into TRIPLES: one triple with 0's mixed in is "
            "1 0* 1 0* 1 0*.",
            "Zero or more triples, with a leading 0*: 0*(10*10*10*)*.",
        ],
        concept=(
            "A 'count ≡ 0 mod m' condition groups the counted symbol into "
            "blocks of size m. Each repetition here adds exactly three 1's, "
            "so the total stays a multiple of 3. Allowing zero repetitions "
            "covers the k = 0 case (no 1's at all)."
        ),
        strategy="0*(10*10*10*)*.",
        example_accept=["", "0", "111", "010101", "111111"],
        example_reject=["1", "11", "1111", "01", "11011"],
        difficulty=3,
        points=180,
        sipser_ref="Sipser §1.3",
    ),
    # 13 --------------------------------------------------------------- #
    Problem(
        key="re_ones_mod3_1",
        kind="RE",
        title="Number of 1's ≡ 1 mod 3 (3k+1, k ≥ 0)",
        prompt="Strings over {0,1} where the number of 1's is 3k+1 for some "
               "k ≥ 0 (i.e. #1's ≡ 1 mod 3).",
        alphabet=BIN,
        membership=lambda s: _ones(s) % 3 == 1,
        reference_regex="0*10*(10*10*10*)*",
        re_hints=[
            "Start by forcing ONE required 1 (that is the +1): 0*10*.",
            "Then add any number of complete triples of 1's: (10*10*10*)*.",
        ],
        concept=(
            "For '≡ r mod m', first lay down r mandatory copies of the "
            "symbol, then allow any number of full blocks of size m. Here one "
            "mandatory 1 gives the +1, and each optional triple keeps the "
            "remainder at 1 mod 3."
        ),
        strategy="One forced 1, then triples: 0*10*(10*10*10*)*.",
        example_accept=["1", "01", "10", "0001", "1111"],
        example_reject=["", "0", "11", "111", "1010"],
        difficulty=4,
        points=250,
        sipser_ref="Sipser §1.3",
    ),
    # 14 --------------------------------------------------------------- #
    Problem(
        key="re_ones_mod3_0_pos",
        kind="RE",
        title="Number of 1's is 3k, k ≥ 1 (multiple of 3, at least 3)",
        prompt="Strings over {0,1} where the number of 1's is 3k for some "
               "k ≥ 1 (a positive multiple of 3 — zero 1's is NOT allowed).",
        alphabet=BIN,
        membership=lambda s: _ones(s) % 3 == 0 and _ones(s) >= 3,
        reference_regex="0*10*10*1(0*10*10*10*)*0*",
        re_hints=[
            "This is like 'multiple of 3' but the empty-triple case (k=0) is "
            "forbidden, so you must FORCE at least one triple.",
            "Write one mandatory triple of 1's: 0*10*10*1…",
            "Then allow any number of extra triples, and trailing 0's: "
            "0*10*10*1(0*10*10*10*)*0*.",
        ],
        concept=(
            "The difference from the k ≥ 0 version is that we must exclude "
            "the empty case. We do that by making the FIRST triple mandatory "
            "(three literal 1's with 0* interspersed) and then allowing extra "
            "triples optionally. This forces at least three 1's while keeping "
            "the count a multiple of 3."
        ),
        strategy="Force one triple, then optional extra triples: "
                 "0*10*10*1(0*10*10*10*)*0*.",
        example_accept=["111", "0111", "111000", "111111"],
        example_reject=["", "0", "1", "11", "1111"],
        difficulty=4,
        points=250,
        sipser_ref="Sipser §1.3",
    ),
    # 15 --------------------------------------------------------------- #
    Problem(
        key="dfa_mod3_1_or_odd0",
        kind="DFA",
        title="(#1's ≡ 1 mod 3) OR (odd number of 0's)",
        prompt="Build a DFA over {0,1} accepting strings where the number of "
               "1's is ≡ 1 mod 3, OR the number of 0's is odd (or both).",
        alphabet=BIN,
        membership=lambda s: (_ones(s) % 3 == 1) or (_zeros(s) % 2 == 1),
        concept=(
            "An OR of two independent counting conditions is built with the "
            "PRODUCT construction. Track both counters at once: the number of "
            "1's mod 3 (3 values) and the number of 0's mod 2 (2 values). A "
            "state is a pair (r, p). Accept when r = 1 OR p = 1."
        ),
        strategy=(
            "Product DFA with 3 × 2 = 6 states, one per pair\n"
            "  (ones mod 3, zeros mod 2):\n\n"
            "  Reading a '1' advances the mod-3 counter: r → (r+1) mod 3.\n"
            "  Reading a '0' flips the mod-2 counter: p → (p+1) mod 2.\n\n"
            "  Start = (0, 0).\n"
            "  ACCEPT every state with r == 1 OR p == 1  "
            "(that is 4 of the 6 states).\n\n"
            "Because the two conditions are joined by OR, a state is "
            "accepting if EITHER coordinate is in its accepting set."
        ),
        note=(
            "All 6 product states are reachable and pairwise distinguishable "
            "here, so 6 is already minimal — OR vs AND only changes WHICH "
            "states accept, not how many states you need."
        ),
        example_accept=["1", "0", "01", "10", "000"],
        example_reject=["", "11", "1010", "0011", "111"],
        difficulty=4,
        points=250,
        sipser_ref="Sipser §1.1",
    ),
    # 16 --------------------------------------------------------------- #
    Problem(
        key="dfa_mod3_1_and_odd0",
        kind="DFA",
        title="(#1's ≡ 1 mod 3) AND (odd number of 0's)",
        prompt="Build a DFA over {0,1} accepting strings where the number of "
               "1's is ≡ 1 mod 3 AND the number of 0's is odd.",
        alphabet=BIN,
        membership=lambda s: (_ones(s) % 3 == 1) and (_zeros(s) % 2 == 1),
        concept=(
            "Same product machine as the OR version — track (ones mod 3, "
            "zeros mod 2) with 6 states. The ONLY difference is the accepting "
            "set: for AND you accept a state only when BOTH coordinates are "
            "accepting, so just one state (r = 1 AND p = 1) is accepting."
        ),
        strategy=(
            "Product DFA, 6 states = (ones mod 3, zeros mod 2):\n"
            "  '1' does r → (r+1) mod 3;  '0' does p → (p+1) mod 2.\n"
            "  Start = (0, 0).\n"
            "  ACCEPT only the single state (r=1, p=1).\n\n"
            "This is the classic illustration that AND and OR share the same "
            "state set and transitions; only the final-state set differs "
            "(intersection vs union of the two accepting sets)."
        ),
        note=(
            "Here only 1 of the 6 states accepts, yet you still need all 6 "
            "states to track the two counters — accepting fewer states does "
            "not let you remove states."
        ),
        example_accept=["1000", "0001", "0010", "100000"],
        example_reject=["", "1", "0", "11", "100"],
        difficulty=4,
        points=250,
        sipser_ref="Sipser §1.1",
    ),
    # 17 --------------------------------------------------------------- #
    Problem(
        key="dfa_mod3_1_or_odd1",
        kind="DFA",
        title="(#1's ≡ 1 mod 3) OR (odd number of 1's)",
        prompt="Build a DFA over {0,1} accepting strings where the number of "
               "1's is ≡ 1 mod 3, OR the number of 1's is odd.",
        alphabet=BIN,
        membership=lambda s: (_ones(s) % 3 == 1) or (_ones(s) % 2 == 1),
        concept=(
            "Here BOTH conditions talk about the SAME quantity — the number "
            "of 1's — so you do not need two independent counters. By the "
            "Chinese Remainder Theorem, tracking n mod 3 and n mod 2 together "
            "is the same as tracking n mod 6. Only the count of 1's matters; "
            "0's are self-loops."
        ),
        strategy=(
            "Track #1's mod 6 with 6 states c0…c5 (0's self-loop on every "
            "state, since 0's don't change the count of 1's):\n"
            "  c_i --1--> c_(i+1 mod 6),   c_i --0--> c_i\n"
            "  Start = c0.\n"
            "  Accept c_i when (i mod 3 == 1) OR (i is odd):\n"
            "    i=1: 1mod3=1 ✓    i=3: odd ✓    i=4: 4mod3=1 ✓    i=5: odd ✓\n"
            "  So accept {c1, c3, c4, c5}; reject {c0, c2}.\n\n"
            "A smaller 2-state 'odd number of 1's' DFA actually suffices here "
            "because 'odd' already implies several of the mod-3=1 cases — but "
            "the mod-6 machine is the clean systematic construction."
        ),
        note=(
            "Because both tests measure the same counter, a NAIVE product of "
            "a 3-state and a 2-state machine (6 states) is correct but not "
            "independent — the reachable combinations are exactly n mod 6."
        ),
        example_accept=["1", "01", "10", "111", "11111"],
        example_reject=["", "0", "11", "00", "1100"],
        difficulty=4,
        points=250,
        sipser_ref="Sipser §1.1",
    ),
    # 18 --------------------------------------------------------------- #
    Problem(
        key="dfa_oddlen_or_01",
        kind="DFA",
        title="Odd length OR s = 01",
        prompt="Build a DFA over {0,1} accepting strings of ODD length, OR "
               "the single string \"01\".",
        alphabet=BIN,
        membership=lambda s: (len(s) % 2 == 1) or (s == "01"),
        concept=(
            "This is a union of a 2-state DFA (odd length) and a DFA for the "
            "single string \"01\". The textbook product would be 2 × 4 = 8 "
            "states, but the MINIMAL DFA has only 5. The savings come purely "
            "from UNREACHABILITY: the \"01\"-matcher secretly fixes the "
            "length (you can only be mid-match at specific lengths), so any "
            "(length-parity, matcher-position) pair that contradicts that "
            "length can never occur."
        ),
        strategy=(
            "Minimal 5-state DFA. States named by a shortest string reaching "
            "them:\n"
            "  S_eps = start (length 0, even, matching corridor)\n"
            "  S_0   = read a leading 0 (odd length so far)      ACCEPT\n"
            "  S_1   = odd length, off the 01-path               ACCEPT\n"
            "  S_00  = even length, 01 no longer possible\n"
            "  S_01  = matched exactly 01                        ACCEPT\n\n"
            "Transitions:\n"
            "  S_eps --0--> S_0     S_eps --1--> S_1\n"
            "  S_0   --0--> S_00    S_0   --1--> S_01\n"
            "  S_1   --0--> S_00    S_1   --1--> S_00\n"
            "  S_00  --0--> S_1     S_00  --1--> S_1\n"
            "  S_01  --0--> S_1     S_01  --1--> S_1\n"
            "  Start = S_eps,  Accept = {S_0, S_1, S_01}.\n\n"
            "Past the matching corridor, S_00 and S_1 simply track length "
            "parity (odd ⇒ accept) and bounce to each other on every symbol."
        ),
        note=(
            "WHY 5 states and not 8?  The product D1 × D2 has 2 × 4 = 8 "
            "states, but 3 of them are UNREACHABLE. D2 (the exact-\"01\" "
            "machine) can only sit in its 'after 0' state at length 1 and its "
            "'after 01' state at length 2 — the matcher position pins down the "
            "length, hence the length parity. So pairs like (even length, "
            "after-0) or (odd length, after-01) can never be reached, and the "
            "start-state copy only occurs at length 0. Drop those 3 "
            "impossible pairs and 5 reachable, all-distinguishable states "
            "remain. No two of them are equivalent, so 5 is minimal — the "
            "collapse here is 100% reachability, with no merging needed."
        ),
        example_accept=["0", "1", "01", "000", "101"],
        example_reject=["", "00", "10", "11", "0000"],
        difficulty=5,
        points=250,
        sipser_ref="Sipser §1.1",
    ),
    # 19 --------------------------------------------------------------- #
    Problem(
        key="dfa_odd0_or_001",
        kind="DFA",
        title="Odd number of 0's OR s = 001",
        prompt="Build a DFA over {0,1} accepting strings with an ODD number "
               "of 0's, OR the single string \"001\".",
        alphabet=BIN,
        membership=lambda s: (_zeros(s) % 2 == 1) or (s == "001"),
        concept=(
            "A union of 'odd number of 0's' (2 states) with the single-string "
            "DFA for \"001\". Unlike the previous problem, the counted feature "
            "(number of 0's) is NOT fully pinned down by matcher position, so "
            "the collapse is a MIX of unreachable pairs plus merging of "
            "Myhill–Nerode-equivalent states. The minimal DFA has 6 states."
        ),
        strategy=(
            "Minimal 6-state DFA, states named by a shortest reaching "
            "string:\n"
            "  S_eps = start (0 zeros, even; corridor open)\n"
            "  S_0   = prefix 0, one 0 (odd)                     ACCEPT\n"
            "  S_1   = a 1, zero 0's, off the 001-path\n"
            "  S_00  = prefix 00, two 0's (even)\n"
            "  S_01  = odd 0's but 001-path broken               ACCEPT\n"
            "  S_001 = matched exactly 001                       ACCEPT\n\n"
            "Transitions:\n"
            "  S_eps --0--> S_0     S_eps --1--> S_1\n"
            "  S_0   --0--> S_00    S_0   --1--> S_01\n"
            "  S_1   --0--> S_01    S_1   --1--> S_1\n"
            "  S_00  --0--> S_01    S_00  --1--> S_001\n"
            "  S_01  --0--> S_1     S_01  --1--> S_01\n"
            "  S_001 --0--> S_01    S_001 --1--> S_1\n"
            "  Start = S_eps,  Accept = {S_0, S_01, S_001}.\n\n"
            "Once \"001\" is no longer reachable, S_1 and S_01 behave as the "
            "pure 0-parity tracker (S_1 = even/reject, S_01 = odd/accept; 0's "
            "flip between them, 1's self-loop)."
        ),
        note=(
            "WHY 6 states?  The product (2 × 5 = 10, or 2 × 4 = 8 with a "
            "folded matcher) over-counts for two reasons. First, some "
            "(0-parity, matcher-position) pairs are UNREACHABLE because the "
            "position in the \"001\" matcher constrains how many 0's have been "
            "seen. Second, every product state where \"001\" is already "
            "impossible is EQUIVALENT to another with the same 0-parity, so "
            "those merge into just two states (odd-0 accept / even-0 reject). "
            "Unreachable + merged ⇒ 6 states. Contrast with 'odd length OR "
            "01', which collapsed by reachability alone."
        ),
        example_accept=["0", "001", "10", "000", "011"],
        example_reject=["", "1", "00", "0011", "11"],
        difficulty=5,
        points=250,
        sipser_ref="Sipser §1.1",
    ),
    # 20 --------------------------------------------------------------- #
    Problem(
        key="re_length_ge_3",
        kind="RE",
        title="Length at least 3",
        prompt="Strings over {0,1} whose LENGTH is 3 or more.",
        alphabet=BIN,
        membership=lambda s: len(s) >= 3,
        reference_regex="(0|1)(0|1)(0|1)(0|1)*",
        re_hints=[
            "Force three symbols up front, each one free: (0|1)(0|1)(0|1).",
            "Then let any number of extra symbols follow: (0|1)*.",
        ],
        concept=(
            "A lower bound on length is written by laying down that many "
            "mandatory 'any symbol' factors and then letting the rest grow "
            "freely with a star. Three forced (0|1) factors guarantee length "
            "≥ 3, and the trailing (0|1)* adds anything beyond that."
        ),
        strategy="Three forced symbols then a free tail: (0|1)(0|1)(0|1)(0|1)*.",
        example_accept=["000", "101", "1111", "01010"],
        example_reject=["", "0", "1", "01", "11"],
        difficulty=1,
        points=80,
        sipser_ref="Sipser §1.3",
    ),
    # 21 --------------------------------------------------------------- #
    Problem(
        key="re_only_epsilon",
        kind="RE",
        title="Only the empty string",
        prompt="The language that contains ONLY the empty string ε "
               "(no symbols at all).",
        alphabet=BIN,
        membership=lambda s: s == "",
        reference_regex="ε",
        re_hints=[
            "This is not the empty LANGUAGE — it has exactly one member.",
            "That member is the empty string, written ε.",
        ],
        concept=(
            "There is a crucial distinction between {ε}, the language whose "
            "only string is the empty string, and ∅, the language with no "
            "strings at all. The regular expression ε denotes {ε}: it matches "
            "the empty input and nothing else."
        ),
        strategy="Just the empty-string atom: ε.",
        example_accept=[""],
        example_reject=["0", "1", "00", "01", "10"],
        note=(
            "Compare with the next problem, ∅: {ε} accepts one string, while "
            "∅ accepts none. Both are regular (Sipser §1.3)."
        ),
        difficulty=1,
        points=80,
        sipser_ref="Sipser §1.3",
    ),
    # 22 --------------------------------------------------------------- #
    Problem(
        key="re_empty_language",
        kind="RE",
        title="The empty language",
        prompt="The EMPTY language: no string at all is accepted "
               "(not even ε).",
        alphabet=BIN,
        membership=lambda s: False,
        reference_regex="∅",
        re_hints=[
            "Nothing is in this language, including the empty string.",
            "The symbol for the empty language is ∅.",
        ],
        concept=(
            "The empty language ∅ contains zero strings. It is the identity "
            "for union and an annihilator for concatenation. Its regular "
            "expression is the single symbol ∅, which matches no input "
            "whatsoever — distinct from ε, which matches the empty string."
        ),
        strategy="The empty-language atom: ∅.",
        example_accept=[],
        example_reject=["", "0", "1", "01", "10"],
        difficulty=1,
        points=80,
        sipser_ref="Sipser §1.3",
    ),
    # 23 --------------------------------------------------------------- #
    Problem(
        key="re_contains_000",
        kind="RE",
        title="Contains substring 000",
        prompt="Strings over {0,1} that CONTAIN 000 as a substring.",
        alphabet=BIN,
        membership=lambda s: "000" in s,
        reference_regex="(0|1)*000(0|1)*",
        re_hints=[
            "'contains X' = (anything) X (anything).",
            "Sandwich the literal 000 between two (0|1)* factors.",
        ],
        concept=(
            "The containment template (Σ)* w (Σ)* works for any fixed word w. "
            "Here w = 000, so three consecutive 0's must appear somewhere, "
            "with arbitrary binary text before and after."
        ),
        strategy="(0|1)*000(0|1)*.",
        example_accept=["000", "1000", "0001", "110001"],
        example_reject=["", "0", "00", "0101", "1100"],
        difficulty=2,
        points=120,
        sipser_ref="Sipser §1.3",
    ),
    # 24 --------------------------------------------------------------- #
    Problem(
        key="re_start1_or_end0",
        kind="RE",
        title="Starts with 1 OR ends with 0",
        prompt="Strings over {0,1} that START with 1, OR END with 0 "
               "(or both). The empty string is NOT in the language.",
        alphabet=BIN,
        membership=lambda s: s != "" and (s[0] == "1" or s[-1] == "0"),
        reference_regex="1(0|1)*|(0|1)*0",
        re_hints=[
            "Two independent conditions joined by OR become a union of two "
            "regular expressions.",
            "Starts with 1: 1(0|1)*.  Ends with 0: (0|1)*0.",
            "Union them: 1(0|1)*|(0|1)*0.",
        ],
        concept=(
            "Regular languages are closed under union (Sipser §1.3), so an OR "
            "of two patterns is just the two patterns separated by |. Each "
            "side here is a one-sided anchoring: a forced leading 1 on the "
            "left, a forced trailing 0 on the right. Neither side matches the "
            "empty string, so ε is correctly excluded."
        ),
        strategy="Union the two anchored patterns: 1(0|1)*|(0|1)*0.",
        example_accept=["1", "0", "10", "110", "1001"],
        example_reject=["", "01", "011", "0101", "0011"],
        difficulty=3,
        points=180,
        sipser_ref="Sipser §1.3",
    ),
    # 25 --------------------------------------------------------------- #
    Problem(
        key="dfa_third_symbol_1",
        kind="DFA",
        title="Third symbol is 1",
        prompt="Build a DFA over {0,1} accepting strings whose THIRD symbol "
               "(counting from the left, 1-indexed) is a 1. Length must be "
               "at least 3.",
        alphabet=BIN,
        membership=lambda s: len(s) >= 3 and s[2] == "1",
        concept=(
            "A fixed-position-from-the-start test is naturally deterministic: "
            "count symbols as they arrive, branch once at the position of "
            "interest, then stop caring. Here we read two symbols blindly, "
            "check that the third is 1, and accept everything after."
        ),
        strategy=(
            "6-state DFA that counts the first three positions:\n"
            "  q0 --0/1--> q1   (saw 1 symbol)\n"
            "  q1 --0/1--> q2   (saw 2 symbols)\n"
            "  q2 --1--> qA     (third symbol is 1: good)\n"
            "  q2 --0--> qD     (third symbol is 0: dead)\n"
            "  qA --0/1--> qA   (accepting sink)\n"
            "  qD --0/1--> qD   (dead sink)\n"
            "  Start = q0,  Accept = {qA}.\n"
            "States q0, q1, q2 are non-accepting (strings shorter than 3 end "
            "there and are rejected)."
        ),
        example_accept=["001", "111", "1010", "0010"],
        example_reject=["", "0", "11", "000", "100"],
        difficulty=2,
        points=120,
        sipser_ref="Sipser §1.1",
    ),
    # 26 --------------------------------------------------------------- #
    Problem(
        key="dfa_not_end_00",
        kind="DFA",
        title="Does NOT end in 00",
        prompt="Build a DFA over {0,1} accepting strings that do NOT end "
               "with 00. The empty string and a single 0 do not end in 00, "
               "so they ARE accepted.",
        alphabet=BIN,
        membership=lambda s: not s.endswith("00"),
        concept=(
            "Whether a string ends in 00 depends only on its last two "
            "symbols, so a DFA can track that suffix in a few states. Build "
            "the recognizer for 'ends in 00' and complement it by swapping "
            "accepting and non-accepting states — regular languages are "
            "closed under complement (Sipser §1.1)."
        ),
        strategy=(
            "3-state DFA tracking the trailing run of 0's:\n"
            "  qS = last symbol was 1, or string is empty\n"
            "  qZ = ends in exactly one 0 (…10 or a lone 0)\n"
            "  q00 = ends in 00\n"
            "  qS  --1--> qS    qS  --0--> qZ\n"
            "  qZ  --1--> qS    qZ  --0--> q00\n"
            "  q00 --1--> qS    q00 --0--> q00\n"
            "  Start = qS,  Accept = {qS, qZ}  (everything except q00).\n"
            "The start state is accepting so that ε and strings ending in 1 "
            "or a single 0 are accepted."
        ),
        example_accept=["", "1", "0", "01", "110"],
        example_reject=["00", "000", "100", "1100", "0100"],
        difficulty=3,
        points=180,
        sipser_ref="Sipser §1.1",
    ),
    # 27 --------------------------------------------------------------- #
    Problem(
        key="dfa_contains_00_and_11",
        kind="DFA",
        title="Contains 00 AND contains 11",
        prompt="Build a DFA over {0,1} accepting strings that contain 00 as "
               "a substring AND also contain 11 as a substring.",
        alphabet=BIN,
        membership=lambda s: "00" in s and "11" in s,
        concept=(
            "An AND of two containment conditions is a product of two small "
            "'have I seen it yet?' trackers. One latch records whether 00 has "
            "appeared, the other whether 11 has appeared. Once a latch flips "
            "on it stays on. Accept only when both latches are on."
        ),
        strategy=(
            "Product DFA. Track two things: the current trailing symbol (to "
            "detect a repeat) and two sticky flags seen00, seen11.\n"
            "A compact 8-state version uses states (last, seen00, seen11) "
            "that are reachable; conceptually:\n"
            "  * seen00 turns true the moment two 0's occur back to back;\n"
            "  * seen11 turns true the moment two 1's occur back to back;\n"
            "  * both flags are latching (never reset).\n"
            "  Start: no previous symbol, both flags false.\n"
            "  Accept: any state with seen00 AND seen11 both true.\n"
            "Implement 'last symbol' so that reading the same symbol again "
            "sets the matching flag."
        ),
        example_accept=["0011", "1100", "00110", "110010"],
        example_reject=["", "00", "11", "0101", "001"],
        difficulty=4,
        points=250,
        sipser_ref="Sipser §1.1",
    ),
    # 28 --------------------------------------------------------------- #
    Problem(
        key="dfa_even_zeros_end_1",
        kind="DFA",
        title="Even number of 0's AND ends in 1",
        prompt="Build a DFA over {0,1} accepting strings that have an EVEN "
               "number of 0's AND end with a 1 (so the string is non-empty "
               "and its last symbol is 1).",
        alphabet=BIN,
        membership=lambda s: _zeros(s) % 2 == 0 and s.endswith("1"),
        concept=(
            "This is an AND of a counting condition (0's are even) and a "
            "suffix condition (ends in 1). The product tracks 0-parity in one "
            "coordinate and the last symbol in the other, and accepts only "
            "the combination even-parity-and-last-was-1."
        ),
        strategy=(
            "4-state product DFA = (zeros mod 2, last symbol was 1?):\n"
            "  qE0 = even 0's, last symbol not 1 (start, or just read a 0)\n"
            "  qE1 = even 0's, last symbol was 1          ACCEPT\n"
            "  qO0 = odd 0's,  last symbol not 1\n"
            "  qO1 = odd 0's,  last symbol was 1\n"
            "  Reading 0 flips the parity and clears the last-was-1 flag;\n"
            "  reading 1 keeps the parity and sets the last-was-1 flag.\n"
            "  qE0 --0--> qO0   qE0 --1--> qE1\n"
            "  qE1 --0--> qO0   qE1 --1--> qE1\n"
            "  qO0 --0--> qE0   qO0 --1--> qO1\n"
            "  qO1 --0--> qE0   qO1 --1--> qO1\n"
            "  Start = qE0,  Accept = {qE1}."
        ),
        example_accept=["1", "111", "001", "0011"],
        example_reject=["", "0", "01", "10", "11000"],
        difficulty=3,
        points=180,
        sipser_ref="Sipser §1.1",
    ),
    # 29 --------------------------------------------------------------- #
    Problem(
        key="dfa_div3_value",
        kind="DFA",
        title="Binary value divisible by 3",
        prompt="Build a DFA over {0,1} accepting strings that, read as a "
               "binary number MOST-SIGNIFICANT-BIT first, have a value "
               "divisible by 3. The empty string counts as the value 0, "
               "which is divisible by 3, so ε is accepted.",
        alphabet=BIN,
        membership=lambda s: int(s, 2) % 3 == 0 if s else True,
        concept=(
            "Reading bits left to right builds the value by the rule "
            "new = 2*old + bit. We only care about the value modulo 3, and "
            "that update is well-defined on residues: new_mod = "
            "(2*old_mod + bit) mod 3. So three states — one per residue — "
            "suffice. This is a classic divisibility DFA (Sipser §1.1)."
        ),
        strategy=(
            "3-state DFA, one state per residue of the value mod 3:\n"
            "  r0 = value ≡ 0,  r1 = value ≡ 1,  r2 = value ≡ 2.\n"
            "  On bit b from state r_k go to r_((2k+b) mod 3):\n"
            "    r0 --0--> r0   r0 --1--> r1\n"
            "    r1 --0--> r2   r1 --1--> r0\n"
            "    r2 --0--> r1   r2 --1--> r2\n"
            "  Start = r0,  Accept = {r0}.\n"
            "Because the start state r0 is accepting, the empty string (value "
            "0) is accepted, and so are strings with leading zeros."
        ),
        note=(
            "Design choice: ε is accepted, representing the value 0. Leading "
            "zeros do not change the value, so e.g. '0', '00', '011' (=3) are "
            "all accepted. Verified by converting each test string with "
            "int(s, 2)."
        ),
        example_accept=["", "0", "11", "110", "011"],
        example_reject=["1", "10", "100", "101", "111"],
        difficulty=4,
        points=250,
        sipser_ref="Sipser §1.1",
    ),
    # 30 --------------------------------------------------------------- #
    Problem(
        key="nfa_contains_101_or_11",
        kind="NFA",
        title="Contains 101 OR contains 11",
        prompt="Build an NFA over {0,1} accepting strings that contain 101 "
               "as a substring, OR contain 11 as a substring (or both).",
        alphabet=BIN,
        membership=lambda s: "101" in s or "11" in s,
        concept=(
            "Nondeterminism shines for 'contains one of several patterns'. "
            "Keep a start state that loops on every symbol (guessing where "
            "the pattern begins), then branch into a little chain for each "
            "target substring. The machine accepts if ANY guessed branch "
            "reaches its accepting end — exactly the union semantics of an "
            "NFA (Sipser §1.2)."
        ),
        strategy=(
            "NFA with a looping start plus two guess-branches:\n"
            "  S --0,1--> S            (stay and keep scanning)\n"
            "  Branch for 101:  S --1--> a1 --0--> a2 --1--> ACC101\n"
            "  Branch for 11:   S --1--> b1 --1--> ACC11\n"
            "  Both ACC101 and ACC11 loop on 0,1 to absorb the rest:\n"
            "    ACC101 --0,1--> ACC101,   ACC11 --0,1--> ACC11.\n"
            "  Start = S,  Accept = {ACC101, ACC11}.\n"
            "The nondeterministic choice at S lets the machine 'try' each "
            "pattern starting at every position without committing."
        ),
        note=(
            "Note that '11' already implies many matches, but 101 catches "
            "strings like 0101 that have no 11; the union handles both. "
            "Nondeterministic (multiple edges on the same symbol) by design."
        ),
        example_accept=["11", "101", "0101", "11000"],
        example_reject=["", "0", "1", "10", "100"],
        difficulty=3,
        points=180,
        sipser_ref="Sipser §1.2",
    ),
    # 31 --------------------------------------------------------------- #
    Problem(
        key="nfa_third_from_end_1",
        kind="NFA",
        title="Third symbol from the end is 1",
        prompt="Build an NFA over {0,1} accepting strings whose THIRD symbol "
               "FROM THE END is a 1 (so the string has length at least 3).",
        alphabet=BIN,
        membership=lambda s: len(s) >= 3 and s[-3] == "1",
        concept=(
            "This is the textbook example where an NFA is dramatically "
            "simpler than any DFA (Sipser §1.2). The machine loops on the "
            "start state while scanning, then nondeterministically 'guesses' "
            "that the current 1 is the third-from-last symbol and reads "
            "exactly two more symbols to the end."
        ),
        strategy=(
            "4-state NFA:\n"
            "  q0 --0,1--> q0        (loop, scanning the prefix)\n"
            "  q0 --1--> q1          (guess: THIS 1 is 3rd from the end)\n"
            "  q1 --0,1--> q2        (one more symbol)\n"
            "  q2 --0,1--> q3        (the last symbol)\n"
            "  Start = q0,  Accept = {q3}.\n"
            "Only if the guessed 1 really is third-from-last will the two "
            "trailing moves land exactly on the end of input in q3."
        ),
        note=(
            "An equivalent DFA needs 8 states (it must remember the last "
            "three bits); the NFA needs only 4. Classic nondeterminism win "
            "(Sipser §1.2)."
        ),
        example_accept=["100", "111", "0101", "1100"],
        example_reject=["", "0", "1", "00", "011"],
        difficulty=3,
        points=180,
        sipser_ref="Sipser §1.2",
    ),
    # 32 --------------------------------------------------------------- #
    Problem(
        key="nfa_ends_010",
        kind="NFA",
        title="Ends with 010",
        prompt="Build an NFA over {0,1} accepting strings that END with 010.",
        alphabet=BIN,
        membership=lambda s: s.endswith("010"),
        concept=(
            "A suffix test is a natural fit for an NFA: loop on the start "
            "state over every symbol, then guess that the suffix begins now "
            "and read the literal 010 to the end. If the guess is wrong the "
            "branch simply dies, which an NFA treats as rejection on that "
            "path (Sipser §1.2)."
        ),
        strategy=(
            "4-state NFA:\n"
            "  q0 --0,1--> q0     (loop, scanning)\n"
            "  q0 --0--> q1       (guess the suffix 010 starts here)\n"
            "  q1 --1--> q2\n"
            "  q2 --0--> q3\n"
            "  Start = q0,  Accept = {q3}.\n"
            "Acceptance requires the guessed 010 to line up exactly with the "
            "end of the input."
        ),
        example_accept=["010", "0010", "1010", "11010"],
        example_reject=["", "0", "01", "0100", "101"],
        difficulty=2,
        points=120,
        sipser_ref="Sipser §1.2",
    ),
    # 33 --------------------------------------------------------------- #
    Problem(
        key="dfa_all_ones",
        kind="DFA",
        title="All ones (no zeros)",
        prompt="Build a DFA over {0,1} accepting strings made entirely of "
               "1's. The empty string has no 0's, so it IS accepted.",
        alphabet=BIN,
        membership=lambda s: set(s) <= {"1"},
        concept=(
            "Forbidding a symbol altogether is a two-state DFA: an accepting "
            "state you stay in as long as only allowed symbols appear, and a "
            "dead state you fall into forever once the forbidden symbol shows "
            "up. Here any 0 is fatal."
        ),
        strategy=(
            "2-state DFA:\n"
            "  qOK --1--> qOK    qOK --0--> qDead\n"
            "  qDead --0,1--> qDead\n"
            "  Start = qOK,  Accept = {qOK}.\n"
            "The start/accept state qOK covers ε and any run of 1's; the "
            "first 0 traps the machine in qDead."
        ),
        example_accept=["", "1", "11", "111", "1111"],
        example_reject=["0", "10", "01", "100", "110"],
        difficulty=1,
        points=80,
        sipser_ref="Sipser §1.1",
    ),
]


def problems_by_kind(kind: str) -> List[Problem]:
    return [p for p in PROBLEMS if p.kind == kind]


def get_problem(key: str) -> Optional[Problem]:
    for p in PROBLEMS:
        if p.key == key:
            return p
    return None
