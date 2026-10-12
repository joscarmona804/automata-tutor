"""
askbot.py
---------
An OFFLINE, standard-library-only question-answering helper for the Automata
Tutor learning game.

A student studying for an exam types a plain-English question — "what is an
accepting state?", "what does epsilon mean?", "how do I convert an NFA to a
DFA?", "I'm stuck" — and gets back a concise, correct answer drawn from the
app's own built-in material (curriculum.py, lessons.py, quiz.py).

Design notes
------------
* No network, no API keys, no third-party dependencies. Pure standard library.
* No tkinter — this is pure logic so the GUI, a CLI, or tests can import it.
* The facts here are our own words, kept tight and exam-correct, and cite the
  relevant Sipser section the rest of the app already references.
* Matching is deliberately simple but robust: token overlap + phrase
  containment + a small synonym table, so natural phrasings still land.

Public API
----------
    Answer                      — dataclass: text, source, followups
    FAQ                         — dataclass: triggers, topic, answer
    FAQS                        — list[FAQ]: the curated knowledge base
    ask(question, problem=None) — Answer: the main entry point
    suggested_questions(problem=None) -> list[str]
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

# We only need the Problem type for optional, task-aware answers. Importing it
# keeps type hints honest; nothing here mutates a Problem.
try:  # pragma: no cover - import shape is environment dependent
    from quiz import Problem
except Exception:  # pragma: no cover
    Problem = object  # type: ignore[assignment,misc]


# ====================================================================== #
# Data structures
# ====================================================================== #
@dataclass
class Answer:
    """A single reply handed back to the UI.

    Attributes:
        text: The concise answer prose shown to the student.
        source: A short provenance label, e.g. "DFA basics (§1.1)" or
            "from this problem", so the student knows where it came from.
        followups: 0-3 short suggested next questions to keep learning.
    """

    text: str
    source: str
    followups: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class FAQ:
    """One curated question/answer entry in the knowledge base.

    Attributes:
        triggers: Keywords/phrases that should route a question here. Matched
            case-insensitively against the normalized question.
        topic: A chapter id ("dfa", "nfa", "epsilon", "regex", "convert") or
            "general"; used to build the source label and bias followups.
        answer: A concise, correct answer in our own words (1-4 sentences),
            citing a Sipser section where relevant.
        label: Optional short human label for the source line. If omitted a
            label is derived from the topic.
        followups: Optional suggested next questions specific to this FAQ.
    """

    triggers: Sequence[str]
    topic: str
    answer: str
    label: str = ""
    followups: Sequence[str] = ()


# ====================================================================== #
# Curated FAQ knowledge base
# ====================================================================== #
# Answers are intentionally tight — this is exam prep, not a textbook. Facts
# are reused from curriculum.py / lessons.py and cite the same Sipser sections.
FAQS: List[FAQ] = [
    # ---- Core objects -------------------------------------------------
    FAQ(
        triggers=["what is a dfa", "dfa", "deterministic finite automaton",
                  "deterministic automaton", "what's a dfa"],
        topic="dfa",
        label="DFA basics (§1.1)",
        answer=(
            "A DFA (deterministic finite automaton) is the simplest machine "
            "model: states Q, alphabet Σ, a start state, accepting states F, "
            "and a transition function δ that gives exactly ONE next state for "
            "every (state, symbol). It reads a string left to right making one "
            "move per symbol and accepts iff it ends in an accepting state. "
            "(§1.1)"
        ),
        followups=["what is an accept state?",
                   "what's the difference between a DFA and NFA?",
                   "what is a dead state?"],
    ),
    FAQ(
        triggers=["what is an nfa", "nfa", "nondeterministic finite automaton",
                  "nondeterministic automaton", "what's an nfa",
                  "nondeterminism"],
        topic="nfa",
        label="NFA basics (§1.2)",
        answer=(
            "An NFA (nondeterministic finite automaton) is like a DFA except "
            "δ(state, symbol) may lead to a SET of states — zero, one, or "
            "many. Think 'guess and verify': it explores all paths at once and "
            "accepts iff AT LEAST ONE path ends in an accepting state. A dead "
            "branch just fails without rejecting the whole run. (§1.2)"
        ),
        followups=["what's the difference between a DFA and NFA?",
                   "why aren't NFAs more powerful than DFAs?",
                   "what is an epsilon transition?"],
    ),
    FAQ(
        triggers=["what is a regular expression", "regular expression", "regex",
                  "regexp", "what's a regex", "re"],
        topic="regex",
        label="Regular expressions (§1.3)",
        answer=(
            "A regular expression describes a language with three operators: "
            "union a|b (either), concatenation ab (one then the other), and "
            "Kleene star a* (zero or more repeats), plus parentheses for "
            "grouping. Regex, NFAs, and DFAs all describe exactly the regular "
            "languages — three views of one class. (§1.3)"
        ),
        followups=["what are the regex operators and their precedence?",
                   "what is the difference between epsilon and empty set?",
                   "what does Kleene star mean?"],
    ),
    FAQ(
        triggers=["what is a state", "state", "what's a state"],
        topic="dfa",
        label="States (§1.1)",
        answer=(
            "A state is the one bounded fact the machine remembers so far — a "
            "parity, the last few symbols, or how much of a pattern has "
            "matched. A finite automaton has finitely many states, which is "
            "exactly why it cannot count without bound. (§1.1)"
        ),
        followups=["what is a start state?",
                   "what is an accept state?",
                   "what is a dead state?"],
    ),
    FAQ(
        triggers=["what is a start state", "start state", "initial state",
                  "q0", "where does it start", "which state do i start in"],
        topic="dfa",
        label="Start state (§1.1)",
        answer=(
            "The start state (q0) is the single state the machine is in before "
            "reading any input. Every run begins there. The empty string ε is "
            "accepted exactly when the start state is itself an accepting "
            "state. (§1.1)"
        ),
        followups=["what is an accept state?",
                   "what does the arrow pointing into a state mean?",
                   "how do I tell if a string is accepted?"],
    ),
    FAQ(
        triggers=["what is an accept state", "what is an accepting state",
                  "accept state", "accepting state", "final state",
                  "double circle", "what does the double circle mean",
                  "double ring", "two circles"],
        topic="dfa",
        label="Accept states (§1.1)",
        answer=(
            "An accept (final) state, drawn as a DOUBLE CIRCLE, marks a "
            "'yes' outcome: the machine accepts a string exactly when its run "
            "ENDS in one of these states. For an NFA you accept if any one "
            "path ends in a double-circle state. (§1.1)"
        ),
        followups=["what does the arrow pointing into a state mean?",
                   "what is a start state?",
                   "how do I tell if a string is accepted?"],
    ),
    FAQ(
        triggers=["what is a transition", "transition", "what's a transition",
                  "transition function", "delta", "arrow between states",
                  "arrows between states"],
        topic="dfa",
        label="Transitions (§1.1)",
        answer=(
            "A transition is an arrow that says 'reading this symbol in this "
            "state, go here'. In a DFA the transition function δ gives exactly "
            "one target per (state, symbol); in an NFA it may give a set, and "
            "an ε-transition moves without reading any symbol at all. (§1.1)"
        ),
        followups=["what does the double circle mean?",
                   "what is an epsilon transition?",
                   "what is the alphabet?"],
    ),
    FAQ(
        triggers=["what does the arrow pointing into a state mean",
                  "arrow into a state", "arrow into the state",
                  "arrow from nowhere", "incoming arrow", "lone arrow",
                  "unlabeled arrow", "what does the arrow mean"],
        topic="dfa",
        label="Start arrow (§1.1)",
        answer=(
            "An arrow that points into a state from nowhere (no source state) "
            "marks the START state — where every run begins. Arrows that go "
            "BETWEEN two states and carry a symbol label are transitions. "
            "(§1.1)"
        ),
        followups=["what is a start state?",
                   "what is a transition?",
                   "what does the double circle mean?"],
    ),
    FAQ(
        triggers=["what is the alphabet", "alphabet", "sigma", "symbols",
                  "what symbols can i use", "input symbols"],
        topic="dfa",
        label="Alphabet (§1.1)",
        answer=(
            "The alphabet Σ is the finite set of input symbols the machine "
            "reads — in this app it is {0, 1}. A string is just a finite "
            "sequence of symbols from the alphabet, and a language is a set of "
            "such strings. (§1.1)"
        ),
        followups=["what is 'the language' of a machine?",
                   "what is a transition?",
                   "what is a state?"],
    ),
    # ---- Epsilon ------------------------------------------------------
    FAQ(
        triggers=["what is an epsilon transition", "epsilon transition",
                  "epsilon", "what does epsilon mean", "epsilon move",
                  "empty move", "free move", "epsilon arrow",
                  "what is epsilon", "e-transition", "e transition"],
        topic="epsilon",
        label="ε-transitions (§1.2)",
        answer=(
            "An ε-transition (epsilon) is a 'free' move: the machine jumps "
            "from one state to another WITHOUT reading any input symbol. "
            "ε-moves make it easy to glue machines together — the core trick "
            "behind turning a regex into an NFA — and they add no extra power. "
            "(§1.2)"
        ),
        followups=["what is epsilon-closure?",
                   "what is the difference between epsilon and empty set?",
                   "how do I convert an NFA to a DFA?"],
    ),
    FAQ(
        triggers=["what is epsilon closure", "epsilon closure", "e-closure",
                  "epsilon-closure", "closure", "e closure"],
        topic="epsilon",
        label="ε-closure (§1.2)",
        answer=(
            "The ε-closure of a set of states S is S together with every state "
            "reachable from it using only ε-arrows (S itself is always "
            "included). You compute it as a fixpoint — keep adding ε-successors "
            "until nothing new appears. Always ε-close the start set, and "
            "ε-close again after every symbol. (§1.2)"
        ),
        followups=["what is an epsilon transition?",
                   "what is the subset construction?",
                   "how do I convert an NFA to a DFA?"],
    ),
    FAQ(
        triggers=["difference between epsilon and empty set",
                  "epsilon vs empty set", "epsilon and empty set",
                  "empty set", "empty language", "empty string",
                  "epsilon vs empty", "what is the empty set",
                  "difference between empty string and empty set"],
        topic="regex",
        label="ε vs ∅ (§1.3)",
        answer=(
            "They are different: ∅ is the EMPTY LANGUAGE — it contains no "
            "strings at all — while ε is the EMPTY STRING, so the language {ε} "
            "contains exactly one string of length zero. Note a* always "
            "includes ε. (§1.3)"
        ),
        followups=["what is a regular expression?",
                   "what are the regex operators and their precedence?",
                   "what does Kleene star mean?"],
    ),
    # ---- DFA vs NFA / power -------------------------------------------
    FAQ(
        triggers=["difference between a dfa and nfa",
                  "difference between dfa and nfa", "dfa vs nfa",
                  "nfa vs dfa", "dfa or nfa", "compare dfa and nfa",
                  "how are dfa and nfa different", "dfa versus nfa"],
        topic="nfa",
        label="DFA vs NFA (§1.2)",
        answer=(
            "In a DFA every (state, symbol) has exactly one move and the path "
            "is unique; in an NFA a symbol may lead to several states or none, "
            "and ε-moves are allowed. A DFA accepts if its single run ends in "
            "an accept state; an NFA accepts if ANY path does. They recognize "
            "the same languages, but NFAs are often much smaller. (§1.2)"
        ),
        followups=["why aren't NFAs more powerful than DFAs?",
                   "what is the subset construction?",
                   "how do I convert an NFA to a DFA?"],
    ),
    FAQ(
        triggers=["why aren't nfas more powerful", "why arent nfas more powerful",
                  "are nfas more powerful", "nfa more powerful",
                  "nfa vs dfa power", "same power", "equivalent power",
                  "why are nfa and dfa equivalent", "is nfa stronger"],
        topic="convert",
        label="NFA ≡ DFA (§1.2)",
        answer=(
            "NFAs are NOT more powerful than DFAs — both recognize exactly the "
            "regular languages. The subset construction turns any NFA into an "
            "equivalent DFA by tracking the SET of states the NFA could be in, "
            "so nondeterminism only buys convenience and smaller size, not "
            "extra expressive power. (§1.2)"
        ),
        followups=["what is the subset construction?",
                   "how do I convert an NFA to a DFA?",
                   "what's the difference between a DFA and NFA?"],
    ),
    # ---- Conversion ---------------------------------------------------
    FAQ(
        triggers=["how do i convert an nfa to a dfa", "convert nfa to dfa",
                  "nfa to dfa", "nfa->dfa", "nfa → dfa", "turn an nfa into a dfa",
                  "make a dfa from an nfa", "determinize"],
        topic="convert",
        label="NFA→DFA (§1.2)",
        answer=(
            "Use the subset construction. The DFA start state is the "
            "ε-closure of the NFA start. For a DFA state S and symbol a, take "
            "every NFA move from the states in S, then its ε-closure — that "
            "set is the next DFA state. A DFA state accepts if its set "
            "contains any NFA accept state; stop when no new subsets appear. "
            "(§1.2)"
        ),
        followups=["what is the subset construction?",
                   "what is epsilon-closure?",
                   "what is a dead state?"],
    ),
    FAQ(
        triggers=["what is the subset construction", "subset construction",
                  "powerset construction", "what is subset construction",
                  "subset method", "set construction"],
        topic="convert",
        label="Subset construction (§1.2)",
        answer=(
            "The subset (powerset) construction builds a DFA whose each state "
            "is a SET of NFA states — exactly the set the NFA could currently "
            "be in. Start = ε-closure of the NFA start; δ'(S, a) = ε-closure "
            "of the union of NFA moves on a from S; a subset accepts if it "
            "contains any NFA accept state. At most 2^n states, usually far "
            "fewer. (§1.2)"
        ),
        followups=["how do I convert an NFA to a DFA?",
                   "what is epsilon-closure?",
                   "why aren't NFAs more powerful than DFAs?"],
    ),
    # ---- Regex detail -------------------------------------------------
    FAQ(
        triggers=["regex operators", "regex precedence", "operator precedence",
                  "precedence", "order of operations", "union concatenation star",
                  "what are the regex operators", "kleene star",
                  "what does kleene star mean", "star operator",
                  "what does star mean", "what does the star mean"],
        topic="regex",
        label="Regex operators (§1.3)",
        answer=(
            "Three operators: union a|b (either), concatenation ab (then), and "
            "Kleene star a* (zero or more repeats). Precedence HIGH→LOW is star "
            "> concatenation > union — like exponent, multiply, add — so a|bc* "
            "means a | (b(c*)). Parenthesize a choice before starring it: "
            "(0|1)*. (§1.3)"
        ),
        followups=["what is the difference between epsilon and empty set?",
                   "what is a regular expression?",
                   "how do I convert an NFA to a DFA?"],
    ),
    # ---- Semantics ----------------------------------------------------
    FAQ(
        triggers=["what is the language of a machine", "the language",
                  "language of a machine", "language of an automaton",
                  "what does the language mean", "l(m)", "what is a language",
                  "language recognized"],
        topic="dfa",
        label="Language L(M) (§1.1)",
        answer=(
            "The language of a machine M, written L(M), is the set of ALL "
            "strings it accepts. Two machines are equivalent exactly when they "
            "accept the same language, and a language is 'regular' precisely "
            "when some finite automaton (equivalently some regex) recognizes "
            "it. (§1.1)"
        ),
        followups=["how do I tell if a string is accepted?",
                   "what is an accept state?",
                   "what is a regular expression?"],
    ),
    FAQ(
        triggers=["how do i tell if a string is accepted", "is a string accepted",
                  "how do i know if a string is accepted", "string accepted",
                  "how do i trace a string", "how do i run a string",
                  "simulate a string", "does the machine accept"],
        topic="dfa",
        label="Accepting a string (§1.1)",
        answer=(
            "Start in the start state (for an NFA, in the ε-closure of the "
            "start) and follow the transitions symbol by symbol. For a DFA the "
            "string is accepted iff the single run ends in an accept state; "
            "for an NFA, iff at least one of the possible paths ends in one. "
            "(§1.1)"
        ),
        followups=["what is an accept state?",
                   "what is 'the language' of a machine?",
                   "what is a dead state?"],
    ),
    # ---- Dead / trap state --------------------------------------------
    FAQ(
        triggers=["what is a dead state", "dead state", "trap state",
                  "sink state", "what is a trap state", "dead end state",
                  "what does the empty set state mean", "garbage state"],
        topic="dfa",
        label="Dead/trap state (§1.1)",
        answer=(
            "A dead (trap/sink) state is a non-accepting state that, once "
            "entered, loops back to itself on every symbol — so the string can "
            "never recover and will be rejected. DFAs use one to stay TOTAL by "
            "absorbing strings that fall out of the pattern; in the subset "
            "construction it is the empty set ∅. (§1.1)"
        ),
        followups=["what is a DFA?",
                   "what is the subset construction?",
                   "how do I tell if a string is accepted?"],
    ),
]


# ====================================================================== #
# Normalization + matching
# ====================================================================== #
# A compact synonym map: alternative phrasings → the canonical token/phrase
# used in FAQ triggers. Applied to the normalized question before scoring.
_SYNONYMS: Dict[str, str] = {
    "final state": "accept state",
    "final states": "accept state",
    "accepting": "accept",
    "double ring": "double circle",
    "two circles": "double circle",
    "empty move": "epsilon",
    "free move": "epsilon",
    "epsilon move": "epsilon",
    "e-transition": "epsilon transition",
    "determinize": "convert nfa to dfa",
    "powerset construction": "subset construction",
    "powerset": "subset",
    "initial state": "start state",
    "q0": "start state",
    "sigma": "alphabet",
    "regexp": "regex",
    "regular expression": "regex",
}

# Words that carry no routing signal; dropped before token overlap scoring.
_STOPWORDS: Set[str] = {
    "a", "an", "the", "is", "are", "do", "does", "i", "to", "of", "in", "on",
    "what", "whats", "how", "why", "me", "my", "you", "it", "its", "that",
    "this", "and", "or", "for", "with", "can", "mean", "means", "explain",
    "tell", "about", "please", "help", "difference", "between", "vs", "versus",
    "s", "be", "get", "there", "here", "when", "which", "if", "so", "as",
}

# Phrases that signal the student wants help with the CURRENT task, not a
# definition. If `problem` is supplied and one of these fires, we answer from
# the problem itself.
_STUCK_PHRASES: Tuple[str, ...] = (
    "i'm stuck", "im stuck", "i am stuck", "stuck",
    "hint", "give me a hint", "need a hint",
    "how do i start", "how to start", "where do i start", "how do i begin",
    "what do i do", "what should i do", "where do i begin",
    "explain this one", "explain this problem", "help with this",
    "help me with this", "i don't get this", "i dont get this",
    "how do i solve this", "how do i build this", "what's the strategy",
    "whats the strategy", "give me a strategy",
)


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation (keep intra-word apostrophes), collapse space."""
    text = text.lower().strip()
    # Normalize common unicode variants to ASCII hints.
    text = text.replace("ε", " epsilon ").replace("∅", " empty set ")
    text = text.replace("→", " to ").replace("->", " to ")
    # Drop punctuation except apostrophes (so "i'm" survives for phrase match).
    text = re.sub(r"[^a-z0-9'\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _apply_synonyms(text: str) -> str:
    """Rewrite known synonym phrases to their canonical form."""
    for alt, canon in _SYNONYMS.items():
        if alt in text:
            text = text.replace(alt, canon)
    return text


def _tokens(text: str) -> Set[str]:
    """Content tokens of a normalized string, with stopwords removed."""
    return {t for t in text.split() if t and t not in _STOPWORDS}


def _looks_like_task_help(norm: str) -> bool:
    """True if the (normalized) question is asking for help on the current task."""
    for phrase in _STUCK_PHRASES:
        p = _normalize(phrase)
        if p and (norm == p or p in norm):
            return True
    return False


def _score_faq(faq: FAQ, norm: str, q_tokens: Set[str]) -> float:
    """Score how well a FAQ matches the question.

    Combines three signals:
      * phrase containment — a full trigger phrase appearing in the question
        is a very strong signal (weighted heavily),
      * token overlap — fraction of trigger tokens present in the question,
      * a small bonus for matching the single longest/most-specific trigger.
    """
    best = 0.0
    for trig in faq.triggers:
        t_norm = _normalize(trig)
        if not t_norm:
            continue
        t_tokens = _tokens(t_norm)

        score = 0.0
        # Strong: the whole trigger phrase is contained in the question.
        if t_norm in norm:
            # Multi-word phrases are far more specific than single words.
            score += 3.0 + 1.5 * (t_norm.count(" "))
        # Token overlap, normalized by trigger size (so short triggers that
        # fully match still score, long ones need more coverage).
        if t_tokens:
            overlap = len(t_tokens & q_tokens)
            if overlap:
                score += 2.0 * (overlap / len(t_tokens))
                # Reward absolute coverage a little too.
                score += 0.4 * overlap
        best = max(best, score)
    return best


def _source_label(faq: FAQ) -> str:
    """Human-friendly provenance label for a FAQ answer."""
    if faq.label:
        return faq.label
    topic_names = {
        "dfa": "DFA basics (§1.1)",
        "nfa": "NFA basics (§1.2)",
        "epsilon": "ε-transitions (§1.2)",
        "regex": "Regular expressions (§1.3)",
        "convert": "Conversions (§1.2–§1.3)",
        "general": "Automata basics",
    }
    return topic_names.get(faq.topic, "Automata basics")


def _trim(text: str, limit: int = 240) -> str:
    """Trim a long field to a sentence-ish snippet for problem answers."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    # Prefer to cut at the last sentence boundary, else last space.
    for sep in (". ", "; ", ", "):
        idx = cut.rfind(sep)
        if idx > limit * 0.5:
            return cut[: idx + 1].strip()
    idx = cut.rfind(" ")
    return (cut[:idx] if idx > 0 else cut).strip() + "…"


# ====================================================================== #
# Problem-aware answers
# ====================================================================== #
def _problem_answer(problem: "Problem") -> Answer:
    """Build a concise 'help with the current task' answer from a Problem."""
    title = getattr(problem, "title", "") or "this problem"
    prompt = getattr(problem, "prompt", "") or ""
    concept = getattr(problem, "concept", "") or ""
    strategy = getattr(problem, "strategy", "") or ""
    kind = getattr(problem, "kind", "") or ""

    parts: List[str] = []
    if prompt:
        parts.append(f"This task ({title}): {_trim(prompt, 180)}")
    if strategy:
        parts.append(f"How to start — {_trim(strategy, 220)}")
    elif concept:
        parts.append(f"Key idea — {_trim(concept, 220)}")

    if not parts:
        parts.append(
            "Read the prompt carefully, decide the single fact each state must "
            "remember, then wire one transition per symbol."
        )

    text = " ".join(parts)

    followups: List[str] = []
    kind_up = kind.upper()
    if kind_up == "DFA":
        followups = ["what is a dead state?",
                     "how do I tell if a string is accepted?",
                     "what is a state?"]
    elif kind_up == "NFA":
        followups = ["what is an epsilon transition?",
                     "what's the difference between a DFA and NFA?",
                     "how do I convert an NFA to a DFA?"]
    elif kind_up == "RE":
        followups = ["what are the regex operators and their precedence?",
                     "what does Kleene star mean?",
                     "what is a regular expression?"]
    else:
        followups = ["what is a state?",
                     "how do I tell if a string is accepted?"]

    return Answer(text=text, source="from this problem", followups=followups[:3])


# ====================================================================== #
# Fallback
# ====================================================================== #
def _topic_question_samples(limit: int = 5) -> List[str]:
    """A few 'you can ask about…' prompts drawn from the FAQ list."""
    seen: Set[str] = set()
    samples: List[str] = []
    for faq in FAQS:
        if not faq.triggers:
            continue
        # Prefer a trigger phrased like a question ("what is …").
        phrase = next(
            (t for t in faq.triggers if t.startswith("what") or t.startswith("how")),
            faq.triggers[0],
        )
        key = phrase.lower()
        if key in seen:
            continue
        seen.add(key)
        q = phrase.strip()
        if not q.endswith("?"):
            q += "?"
        samples.append(q[0].upper() + q[1:])
        if len(samples) >= limit:
            break
    return samples


def _fallback_answer() -> Answer:
    """Graceful reply when nothing matched: steer the student to real topics."""
    samples = _topic_question_samples(5)
    bullet = "  • " + "\n  • ".join(samples)
    text = (
        "I'm not sure which concept you mean. I can help with the Chapter 1 "
        "automata-theory basics — try asking something like:\n"
        f"{bullet}\n"
        "You can also open the Cheat Sheets for a quick per-chapter summary."
    )
    return Answer(
        text=text,
        source="general",
        followups=["what is a DFA?",
                   "what does epsilon mean?",
                   "how do I convert an NFA to a DFA?"],
    )


# ====================================================================== #
# Public API
# ====================================================================== #
def ask(question: str, problem: Optional["Problem"] = None) -> Answer:
    """Answer a plain-English study question.

    Args:
        question: The student's free-text question.
        problem: Optional current quiz.Problem. When provided and the question
            is clearly about the task at hand ("i'm stuck", "hint", "how do I
            start"), the answer is drawn from that problem and the source is
            set to "from this problem".

    Returns:
        An Answer with concise text, a short source label, and 1-3 followups.
    """
    if not question or not question.strip():
        return _fallback_answer()

    norm = _apply_synonyms(_normalize(question))
    q_tokens = _tokens(norm)

    # Task-aware path: only when we actually have a problem to lean on.
    if problem is not None and _looks_like_task_help(norm):
        return _problem_answer(problem)

    # Score every FAQ and take the best.
    best_faq: Optional[FAQ] = None
    best_score = 0.0
    for faq in FAQS:
        score = _score_faq(faq, norm, q_tokens)
        if score > best_score:
            best_score = score
            best_faq = faq

    # Threshold: require a modest signal so random text falls through.
    if best_faq is None or best_score < 1.5:
        return _fallback_answer()

    followups = list(best_faq.followups)[:3]
    if not followups:
        followups = ["what is a DFA?", "what does epsilon mean?"]
    return Answer(
        text=best_faq.answer,
        source=_source_label(best_faq),
        followups=followups,
    )


def suggested_questions(problem: Optional["Problem"] = None) -> List[str]:
    """Return 4-6 starter questions for the UI.

    If a problem is given, the list is biased toward its chapter/kind so the
    suggestions feel relevant to what the student is working on.
    """
    general = [
        "What is a DFA?",
        "What's the difference between a DFA and NFA?",
        "What does epsilon mean?",
        "How do I convert an NFA to a DFA?",
        "What does the double circle mean?",
        "What is a regular expression?",
    ]
    if problem is None:
        return general[:6]

    chapter = (getattr(problem, "chapter", "") or "").lower()
    kind = (getattr(problem, "kind", "") or "").upper()

    biased: List[str] = ["I'm stuck — how do I start?"]
    by_chapter: Dict[str, List[str]] = {
        "dfa": ["What is a state?",
                "What is a dead state?",
                "How do I tell if a string is accepted?"],
        "nfa": ["What is an NFA?",
                "What's the difference between a DFA and NFA?",
                "What is an epsilon transition?"],
        "epsilon": ["What is an epsilon transition?",
                    "What is epsilon-closure?",
                    "What is the difference between epsilon and empty set?"],
        "regex": ["What are the regex operators and their precedence?",
                  "What does Kleene star mean?",
                  "What is the difference between epsilon and empty set?"],
        "convert": ["What is the subset construction?",
                    "How do I convert an NFA to a DFA?",
                    "Why aren't NFAs more powerful than DFAs?"],
    }
    biased += by_chapter.get(chapter, [])

    if kind == "RE" and "What is a regular expression?" not in biased:
        biased.append("What is a regular expression?")

    # Pad from the general list without duplicating.
    for q in general:
        if len(biased) >= 6:
            break
        if q not in biased:
            biased.append(q)

    return biased[:6]
