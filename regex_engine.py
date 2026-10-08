"""
regex_engine.py
---------------
A tiny formal-language regular-expression engine supporting exactly the
operators taught in an automata course:

    |      union / alternation
    *      Kleene star (zero or more)
    ()     grouping
    .      explicit concatenation is implicit (no operator needed)
    ε      the empty string (also written as the literal 'e' is NOT assumed)
    ∅      the empty language

Concatenation is implicit, e.g. "ab" means a·b. Precedence (high -> low):
    star  >  concatenation  >  union

The engine compiles an RE into an NFA via Thompson's construction and then
simulates it. This keeps semantics identical to what students learn, and it
avoids the quirks of Python's `re` (which uses greedy/backtracking matching
and a very different operator set).
"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple

EPS = "ε"


class RegexError(Exception):
    pass


# ---------------------------------------------------------------------- #
# Thompson NFA: states are ints, transitions map (state, symbol) -> set
# ---------------------------------------------------------------------- #
class _Frag:
    """A compiled NFA fragment with a single start and single accept state."""
    __slots__ = ("start", "accept")

    def __init__(self, start: int, accept: int):
        self.start = start
        self.accept = accept


class RegexNFA:
    def __init__(self) -> None:
        self.n = 0
        self.trans: Dict[Tuple[int, str], Set[int]] = {}
        self.start = 0
        self.accept = 0

    def new_state(self) -> int:
        s = self.n
        self.n += 1
        return s

    def add(self, src: int, sym: str, dst: int) -> None:
        self.trans.setdefault((src, sym), set()).add(dst)

    def closure(self, states: Set[int]) -> Set[int]:
        stack = list(states)
        seen = set(states)
        while stack:
            s = stack.pop()
            for nxt in self.trans.get((s, EPS), ()):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return seen

    def matches(self, word: str) -> bool:
        cur = self.closure({self.start})
        for ch in word:
            nxt: Set[int] = set()
            for s in cur:
                nxt |= self.trans.get((s, ch), set())
            cur = self.closure(nxt)
            if not cur:
                return False
        return self.accept in cur


# ---------------------------------------------------------------------- #
# Parser  ->  Thompson construction
# ---------------------------------------------------------------------- #
class _Compiler:
    def __init__(self, pattern: str, alphabet: Set[str]):
        # Normalise common ASCII stand-ins for the formal symbols.
        self.src = pattern.replace("+", "|")  # tolerate '+' used as union
        self.pos = 0
        self.alphabet = alphabet
        self.nfa = RegexNFA()

    # -- lexer helpers --
    def _peek(self) -> str:
        return self.src[self.pos] if self.pos < len(self.src) else ""

    def _next(self) -> str:
        ch = self.src[self.pos]
        self.pos += 1
        return ch

    # -- grammar --
    #   expr   := term ('|' term)*
    #   term   := factor+                (implicit concatenation)
    #   factor := atom '*'*
    #   atom   := symbol | '(' expr ')' | 'ε' | '∅'
    def compile(self) -> RegexNFA:
        # strip whitespace entirely (formal REs ignore spacing)
        self.src = "".join(self.src.split())
        if self.src == "":
            # empty pattern == language {ε}
            frag = self._lit(EPS)
        else:
            frag = self._expr()
            if self.pos != len(self.src):
                raise RegexError(
                    f"Unexpected character '{self._peek()}' at position "
                    f"{self.pos}."
                )
        self.nfa.start = frag.start
        self.nfa.accept = frag.accept
        return self.nfa

    def _expr(self) -> _Frag:
        frag = self._term()
        while self._peek() == "|":
            self._next()
            rhs = self._term()
            frag = self._union(frag, rhs)
        return frag

    def _term(self) -> _Frag:
        # concatenate factors until we hit ) | or end
        frag = None
        while self._peek() not in ("", "|", ")"):
            f = self._factor()
            frag = f if frag is None else self._concat(frag, f)
        if frag is None:
            # empty term (e.g. "a|") -> epsilon
            frag = self._lit(EPS)
        return frag

    def _factor(self) -> _Frag:
        frag = self._atom()
        while self._peek() == "*":
            self._next()
            frag = self._star(frag)
        return frag

    def _atom(self) -> _Frag:
        ch = self._peek()
        if ch == "(":
            self._next()
            frag = self._expr()
            if self._peek() != ")":
                raise RegexError("Missing closing parenthesis ')'.")
            self._next()
            return frag
        if ch in ("*", "|", ")", ""):
            raise RegexError(f"Unexpected token '{ch or 'end of input'}'.")
        self._next()
        if ch == "∅":
            return self._empty_language()
        if ch == "ε":
            return self._lit(EPS)
        # a literal alphabet symbol
        if self.alphabet and ch not in self.alphabet:
            raise RegexError(
                f"Symbol '{ch}' is not in the alphabet "
                f"{{{', '.join(sorted(self.alphabet))}}}."
            )
        return self._lit(ch)

    # -- Thompson fragment builders --
    def _lit(self, sym: str) -> _Frag:
        s = self.nfa.new_state()
        a = self.nfa.new_state()
        self.nfa.add(s, sym, a)
        return _Frag(s, a)

    def _empty_language(self) -> _Frag:
        # start and accept exist but are disconnected -> matches nothing
        s = self.nfa.new_state()
        a = self.nfa.new_state()
        return _Frag(s, a)

    def _concat(self, f1: _Frag, f2: _Frag) -> _Frag:
        self.nfa.add(f1.accept, EPS, f2.start)
        return _Frag(f1.start, f2.accept)

    def _union(self, f1: _Frag, f2: _Frag) -> _Frag:
        s = self.nfa.new_state()
        a = self.nfa.new_state()
        self.nfa.add(s, EPS, f1.start)
        self.nfa.add(s, EPS, f2.start)
        self.nfa.add(f1.accept, EPS, a)
        self.nfa.add(f2.accept, EPS, a)
        return _Frag(s, a)

    def _star(self, f: _Frag) -> _Frag:
        s = self.nfa.new_state()
        a = self.nfa.new_state()
        self.nfa.add(s, EPS, f.start)
        self.nfa.add(s, EPS, a)
        self.nfa.add(f.accept, EPS, f.start)
        self.nfa.add(f.accept, EPS, a)
        return _Frag(s, a)


def compile_regex(pattern: str, alphabet: Set[str]) -> RegexNFA:
    """Compile `pattern` into an NFA, raising RegexError on bad syntax."""
    return _Compiler(pattern, set(alphabet)).compile()


def regex_matches(pattern: str, word: str, alphabet: Set[str]) -> bool:
    """Does `pattern` match `word` exactly (whole-string match)?"""
    return compile_regex(pattern, alphabet).matches(word)
