"""
game.py
-------
Pure-logic game engine that turns the ``quiz`` problem bank into a
progressive, replayable campaign. There is **no** GUI code here and **no**
dependency on ``tkinter`` or any third-party package -- only the Python
standard library. The Tkinter front end (``app.py``) consumes this module.

Chapter-based progression
==========================
Progression is organised by **chapter** (see :mod:`curriculum`), not by
difficulty. The campaign walks the chapters in curriculum order --
``dfa -> nfa -> epsilon -> regex -> convert`` -- and a chapter opens only once
the *previous* chapter has been solved to at least :data:`UNLOCK_RATIO`
(about 70%). The first chapter (``dfa``) is always unlocked, and an empty
chapter (no problems) counts as cleared so it never blocks the chain.

What this module gives the UI
=============================
* :class:`GameState` -- the serialisable player profile (XP, streak, stars,
  which problems are solved, and -- derived -- which chapters are unlocked).
* Progression rules -- :meth:`GameState.is_unlocked`,
  :meth:`GameState.available_problems`,
  :meth:`GameState.is_chapter_unlocked`,
  :meth:`GameState.highest_unlocked_chapter_index`.
* Scoring -- :meth:`GameState.record_solve` awards XP (base = the problem's
  ``points``), applies a per-hint penalty, grants bonuses for a clean solve
  and for streaks, and tracks a 0..3 star rating per problem.
* An XP -> player-level curve (:meth:`GameState.player_level`,
  :meth:`GameState.xp_to_next_level`).
* Persistence to ``~/.automata_tutor/progress.json`` with graceful recovery
  from a missing or corrupt file.
* :meth:`GameState.level_summary` -- a compact, per-chapter roll-up the GUI
  renders as a campaign map (a list of :class:`ChapterSummary`).

Design notes
============
The engine never imports or holds references to :class:`quiz.Problem` objects
inside :class:`GameState` -- only the small set of metadata it needs
(``key``, ``chapter``, ``points``) is read on demand through the module
functions. That keeps the saved state tiny and decoupled from the exact shape
of the problem bank.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

import curriculum
import quiz


# --------------------------------------------------------------------------- #
# Tunable game-balance constants (all documented, all pure data).
# --------------------------------------------------------------------------- #

#: Fraction of a chapter that must be solved before the next chapter opens.
#: Chapter ``n`` is unlocked when the chapter immediately before it (in
#: curriculum order) is at least this proportion solved. The first chapter is
#: always unlocked. ~0.70 == "about 70%".
UNLOCK_RATIO: float = 0.70

#: Hint penalty: each hint used multiplies the award by (1 - this), i.e. a
#: 25% reduction per hint...
HINT_PENALTY_PER_HINT: float = 0.25

#: ...but never below this fraction of the base award (floor at 25%).
HINT_PENALTY_FLOOR: float = 0.25

#: Flat bonus (fraction of base points) for solving with no wrong attempts.
CLEAN_SOLVE_BONUS: float = 0.20

#: Per-point-of-current-streak bonus, as a fraction of base points, capped by
#: :data:`STREAK_BONUS_CAP`. e.g. a streak of 4 adds 4 * 0.05 = 20%.
STREAK_BONUS_PER: float = 0.05
STREAK_BONUS_CAP: float = 0.50

#: When a solved problem is solved again, XP is only this fraction of what a
#: fresh solve would have earned (you can still improve your star rating).
REPLAY_XP_FRACTION: float = 0.10

#: Player-level curve. Thresholds are cumulative XP needed to *reach* each
#: level; the curve grows quadratically so later levels take longer.
#: level n (1-indexed) requires LEVEL_BASE * (n-1)^2 cumulative XP.
LEVEL_BASE: int = 150


def _xp_for_level(level: int) -> int:
    """Cumulative XP required to have *reached* ``level`` (level 1 == 0 XP)."""
    if level <= 1:
        return 0
    return LEVEL_BASE * (level - 1) * (level - 1)


# --------------------------------------------------------------------------- #
# Curriculum / chapter helpers (read-only views over curriculum.CHAPTERS).
# --------------------------------------------------------------------------- #

def chapter_ids() -> List[str]:
    """Every chapter id, in curriculum (campaign) order."""
    return [c.cid for c in curriculum.CHAPTERS]


def chapter_title(cid: str) -> str:
    """Display title for a chapter id (falls back to the id itself)."""
    return curriculum.get_chapter(cid).title


# --------------------------------------------------------------------------- #
# Problem-bank helpers (read-only views over quiz.PROBLEMS).
# --------------------------------------------------------------------------- #

def _all_keys() -> List[str]:
    """Every problem key in the bank, in bank order."""
    return [p.key for p in quiz.PROBLEMS]


def _chapter_of(problem_key: str) -> Optional[str]:
    """Chapter id for ``problem_key``, or ``None`` if the key is unknown."""
    p = quiz.get_problem(problem_key)
    return None if p is None else str(p.chapter)


def _points_of(problem_key: str) -> int:
    """Base points for ``problem_key`` (0 if the key is unknown)."""
    p = quiz.get_problem(problem_key)
    return 0 if p is None else int(p.points)


def _keys_in_chapter(cid: str) -> List[str]:
    """Keys of every problem belonging to chapter ``cid``.

    Problems are returned sorted by their ``order`` field (lower first), with
    bank order as the tie-breaker, matching the curriculum's intended path
    through a chapter.
    """
    indexed = [
        (p.order, i, p.key)
        for i, p in enumerate(quiz.PROBLEMS)
        if str(p.chapter) == cid
    ]
    indexed.sort()
    return [key for _, _, key in indexed]


# --------------------------------------------------------------------------- #
# Result objects.
# --------------------------------------------------------------------------- #

@dataclass
class SolveOutcome:
    """Everything the UI needs to animate the result of a solve.

    Attributes:
        problem_key: The problem that was solved.
        xp_gained: XP actually added to the profile for this solve (already
            reduced for a replay, if applicable).
        stars: The star rating now held for this problem (0..3).
        stars_delta: Change in stars vs. before this solve (>= 0).
        first_time: ``True`` if this was the first successful solve.
        total_xp: The profile's total XP after applying this solve.
        player_level: The player level after this solve.
        level_up: ``True`` if the player level increased due to this solve.
        newly_unlocked_chapters: Chapter ids that opened up because of this
            solve, in curriculum order (empty if nothing new unlocked).
        newly_unlocked: Backward-compatible alias carrying the same chapter
            ids as :attr:`newly_unlocked_chapters` (the old field used to
            carry difficulty tiers; it now carries chapter ids so existing
            callers keep working).
        unlocked_chapter_index: Index (in curriculum order) of the highest
            chapter now unlocked.
        unlocked_difficulty: Backward-compatible alias for
            :attr:`unlocked_chapter_index` expressed as a 1-based number, so
            older UI code that read ``unlocked_difficulty`` still gets a
            sensible, monotonically-growing integer.
    """

    problem_key: str
    xp_gained: int
    stars: int
    stars_delta: int
    first_time: bool
    total_xp: int
    player_level: int
    level_up: bool
    newly_unlocked_chapters: List[str] = field(default_factory=list)
    newly_unlocked: List[str] = field(default_factory=list)
    unlocked_chapter_index: int = 0
    unlocked_difficulty: int = 1


@dataclass
class ChapterSummary:
    """Per-chapter roll-up for the campaign map (see level_summary).

    Attributes:
        chapter_id: Stable chapter id (e.g. ``"dfa"``).
        title: Display title taken from the curriculum.
        total: Problems that exist in this chapter.
        solved: Problems solved in this chapter.
        stars_earned: Sum of per-problem stars in this chapter.
        stars_possible: ``3 * total``.
        unlocked: Whether this chapter is playable yet.
        solved_ratio: ``solved / total`` (0.0 when the chapter is empty).
        difficulty: Backward-compatible 1-based campaign position of this
            chapter, so older UI code that read ``summary.difficulty`` keeps
            getting a stable, ascending integer per card.
    """

    chapter_id: str
    title: str
    total: int
    solved: int
    stars_earned: int
    stars_possible: int
    unlocked: bool
    solved_ratio: float
    difficulty: int = 0


#: Backward-compatible alias: older code may still import ``TierSummary``.
TierSummary = ChapterSummary


# --------------------------------------------------------------------------- #
# The player profile.
# --------------------------------------------------------------------------- #

@dataclass
class GameState:
    """Serialisable player profile and the home of all progression logic.

    All collections default to empty via :func:`dataclasses.field` so a brand
    new :class:`GameState` represents a fresh player: no XP, nothing solved,
    only the first curriculum chapter unlocked.
    """

    total_xp: int = 0
    solved: Set[str] = field(default_factory=set)
    current_streak: int = 0
    best_streak: int = 0
    hints_used: Dict[str, int] = field(default_factory=dict)
    per_problem_stars: Dict[str, int] = field(default_factory=dict)
    #: Derived cache: index (in curriculum order) of the highest unlocked
    #: chapter. Always recomputed from ``solved`` -- never trusted from disk.
    unlocked_chapter_index: int = 0

    # ----------------------------------------------------------------- #
    # Progression / unlock logic.
    # ----------------------------------------------------------------- #
    def _chapter_solved_ratio(self, cid: str) -> float:
        """Fraction of chapter ``cid`` that is solved (empty chapter -> 1.0).

        An empty chapter counts as fully cleared so it never blocks the
        progression chain.
        """
        keys = _keys_in_chapter(cid)
        if not keys:
            return 1.0
        done = sum(1 for k in keys if k in self.solved)
        return done / len(keys)

    def _is_chapter_cleared(self, cid: str) -> bool:
        """Has chapter ``cid`` been solved to at least :data:`UNLOCK_RATIO`?"""
        return self._chapter_solved_ratio(cid) >= UNLOCK_RATIO

    def highest_unlocked_chapter_index(self) -> int:
        """Compute (not read) the highest unlocked chapter index.

        The first chapter (index 0) is always open. Each subsequent chapter
        opens once the chapter immediately before it is cleared to at least
        :data:`UNLOCK_RATIO`. Empty chapters are treated as cleared, so a gap
        in the problem bank never stops the chain. The returned value is also
        what gets cached in :attr:`unlocked_chapter_index` after any solve.
        """
        cids = chapter_ids()
        if not cids:
            return 0
        unlocked = 0
        for i in range(1, len(cids)):
            if self._is_chapter_cleared(cids[i - 1]):
                unlocked = i
            else:
                break
        return unlocked

    def _refresh_unlocked(self) -> None:
        """Recompute and store :attr:`unlocked_chapter_index`."""
        self.unlocked_chapter_index = self.highest_unlocked_chapter_index()

    def is_chapter_unlocked(self, cid: str) -> bool:
        """Is chapter ``cid`` currently playable?

        Unknown chapter ids are reported as locked. A known chapter is
        unlocked when its position in curriculum order is at or below
        :meth:`highest_unlocked_chapter_index`.
        """
        order = curriculum.chapter_order(cid)
        if order >= len(curriculum.CHAPTERS):
            return False
        return order <= self.highest_unlocked_chapter_index()

    def is_unlocked(self, problem_key: str) -> bool:
        """Is ``problem_key`` currently playable?

        Unknown keys are reported as locked. A known problem is unlocked iff
        its chapter is unlocked.
        """
        cid = _chapter_of(problem_key)
        if cid is None:
            return False
        return self.is_chapter_unlocked(cid)

    def available_problems(self) -> List[str]:
        """Every currently-unlocked problem key, in bank order."""
        return [k for k in _all_keys() if self.is_unlocked(k)]

    # ----------------------------------------------------------------- #
    # Scoring.
    # ----------------------------------------------------------------- #
    @staticmethod
    def _stars_for(hints_used: int, had_wrong_attempt: bool) -> int:
        """Star rating for a solve.

        * 3 stars: no hints and no wrong attempts (a clean solve).
        * 2 stars: a little help -- at most one hint and no wrong attempts.
        * 1 star:  solved with more help or after a wrong attempt.
        """
        if hints_used == 0 and not had_wrong_attempt:
            return 3
        if hints_used <= 1 and not had_wrong_attempt:
            return 2
        return 1

    def _award_for(
        self, problem_key: str, hints_used: int, had_wrong_attempt: bool
    ) -> int:
        """Full (first-time) XP award for a solve, before the replay discount.

        base -> hint penalty -> clean-solve bonus + streak bonus. The streak
        bonus uses the streak value *including* this solve.
        """
        base = _points_of(problem_key)
        if base <= 0:
            return 0

        # Hint penalty: multiplicative, floored.
        multiplier = max(
            HINT_PENALTY_FLOOR,
            1.0 - HINT_PENALTY_PER_HINT * max(0, hints_used),
        )
        award = base * multiplier

        # Bonuses are expressed as fractions of base points.
        bonus_fraction = 0.0
        if not had_wrong_attempt:
            bonus_fraction += CLEAN_SOLVE_BONUS
        # Streak after this solve (current_streak is bumped before we score).
        streak_bonus = min(
            STREAK_BONUS_CAP, STREAK_BONUS_PER * max(0, self.current_streak)
        )
        bonus_fraction += streak_bonus

        award += base * bonus_fraction
        return int(round(award))

    def record_solve(
        self,
        problem_key: str,
        hints_used: int = 0,
        had_wrong_attempt: bool = False,
    ) -> SolveOutcome:
        """Register a successful solve and return a :class:`SolveOutcome`.

        Awards XP, advances the streak, updates the star rating, and
        recomputes which chapters are unlocked.

        Re-solving an already-solved problem is allowed: XP is reduced to
        :data:`REPLAY_XP_FRACTION` of a fresh award, but the star rating can
        still be *improved* (never lowered).

        Args:
            problem_key: Key of the solved problem. Unknown keys are a no-op
                that still returns a well-formed outcome.
            hints_used: Number of hints consumed on this attempt (clamped to
                >= 0).
            had_wrong_attempt: Whether the player submitted a wrong answer
                before getting it right.

        Returns:
            A :class:`SolveOutcome` describing the XP, stars, any level-up,
            and any chapters this solve newly unlocked.
        """
        hints_used = max(0, int(hints_used))

        # Unknown key: do nothing meaningful but stay well-formed.
        if quiz.get_problem(problem_key) is None:
            self._refresh_unlocked()
            return SolveOutcome(
                problem_key=problem_key,
                xp_gained=0,
                stars=0,
                stars_delta=0,
                first_time=False,
                total_xp=self.total_xp,
                player_level=self.player_level(),
                level_up=False,
                newly_unlocked_chapters=[],
                newly_unlocked=[],
                unlocked_chapter_index=self.unlocked_chapter_index,
                unlocked_difficulty=self.unlocked_chapter_index + 1,
            )

        first_time = problem_key not in self.solved
        level_before = self.player_level()
        unlocked_before = self.highest_unlocked_chapter_index()

        # A successful solve extends the streak.
        self.current_streak += 1
        self.best_streak = max(self.best_streak, self.current_streak)

        # Record the (latest) hint count for this problem.
        self.hints_used[problem_key] = hints_used

        # Score it. Replays earn only a small fraction.
        full_award = self._award_for(problem_key, hints_used, had_wrong_attempt)
        xp_gained = (
            full_award if first_time
            else int(round(full_award * REPLAY_XP_FRACTION))
        )
        self.total_xp += xp_gained

        # Stars: never regress, only improve.
        new_stars = self._stars_for(hints_used, had_wrong_attempt)
        old_stars = self.per_problem_stars.get(problem_key, 0)
        stars = max(old_stars, new_stars)
        self.per_problem_stars[problem_key] = stars
        stars_delta = stars - old_stars

        # Mark solved and recompute unlocks.
        self.solved.add(problem_key)
        self._refresh_unlocked()

        unlocked_after = self.unlocked_chapter_index
        cids = chapter_ids()
        newly_unlocked_chapters = [
            cids[i]
            for i in range(unlocked_before + 1, unlocked_after + 1)
            if 0 <= i < len(cids)
        ]
        level_after = self.player_level()

        return SolveOutcome(
            problem_key=problem_key,
            xp_gained=xp_gained,
            stars=stars,
            stars_delta=stars_delta,
            first_time=first_time,
            total_xp=self.total_xp,
            player_level=level_after,
            level_up=level_after > level_before,
            newly_unlocked_chapters=newly_unlocked_chapters,
            newly_unlocked=list(newly_unlocked_chapters),
            unlocked_chapter_index=unlocked_after,
            unlocked_difficulty=unlocked_after + 1,
        )

    def record_wrong_attempt(self, problem_key: str) -> None:
        """Register a wrong submission: resets the current streak to zero.

        The best streak is preserved. ``problem_key`` is accepted for a
        symmetric API and for future per-problem bookkeeping, but the only
        effect today is breaking the active streak.
        """
        self.current_streak = 0

    # ----------------------------------------------------------------- #
    # XP -> player-level curve.
    # ----------------------------------------------------------------- #
    def player_level(self) -> int:
        """Current player level (1-indexed) implied by :attr:`total_xp`."""
        level = 1
        while self.total_xp >= _xp_for_level(level + 1):
            level += 1
        return level

    def xp_to_next_level(self) -> int:
        """XP still needed to reach the next player level (0 at a boundary)."""
        nxt = self.player_level() + 1
        return max(0, _xp_for_level(nxt) - self.total_xp)

    # ----------------------------------------------------------------- #
    # Campaign-map roll-up.
    # ----------------------------------------------------------------- #
    def level_summary(self) -> List[ChapterSummary]:
        """Per-chapter summary for rendering a campaign map.

        Returns one :class:`ChapterSummary` per chapter in curriculum order,
        reporting the chapter id and title, how many problems exist, how many
        are solved, stars earned vs. possible, whether the chapter is
        unlocked, and the solved ratio.
        """
        unlocked_to = self.highest_unlocked_chapter_index()
        out: List[ChapterSummary] = []
        for index, cid in enumerate(chapter_ids()):
            keys = _keys_in_chapter(cid)
            total = len(keys)
            solved = sum(1 for k in keys if k in self.solved)
            stars_earned = sum(self.per_problem_stars.get(k, 0) for k in keys)
            out.append(
                ChapterSummary(
                    chapter_id=cid,
                    title=chapter_title(cid),
                    total=total,
                    solved=solved,
                    stars_earned=stars_earned,
                    stars_possible=3 * total,
                    unlocked=index <= unlocked_to,
                    solved_ratio=(solved / total) if total else 0.0,
                    difficulty=index + 1,
                )
            )
        return out

    # ----------------------------------------------------------------- #
    # (De)serialisation.
    # ----------------------------------------------------------------- #
    def to_dict(self) -> Dict[str, object]:
        """Plain-``dict`` snapshot suitable for :func:`json.dump`."""
        return {
            "version": 2,
            "total_xp": self.total_xp,
            "solved": sorted(self.solved),
            "current_streak": self.current_streak,
            "best_streak": self.best_streak,
            "hints_used": dict(self.hints_used),
            "per_problem_stars": dict(self.per_problem_stars),
            "unlocked_chapter_index": self.unlocked_chapter_index,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "GameState":
        """Rebuild a :class:`GameState` from :meth:`to_dict` output.

        Unknown or malformed fields fall back to sensible defaults so a
        partially-corrupt-but-parseable file still yields a usable profile.
        The unlock level is always re-derived from ``solved`` and never
        trusted from disk, so an older v1 save (which stored
        ``unlocked_difficulty``) upgrades cleanly.
        """
        def _as_int(value: object, default: int = 0) -> int:
            try:
                return int(value)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return default

        solved_raw = data.get("solved", [])
        solved: Set[str] = set()
        if isinstance(solved_raw, (list, tuple, set)):
            solved = {str(k) for k in solved_raw}

        hints_raw = data.get("hints_used", {})
        hints_used: Dict[str, int] = {}
        if isinstance(hints_raw, dict):
            hints_used = {str(k): _as_int(v) for k, v in hints_raw.items()}

        stars_raw = data.get("per_problem_stars", {})
        per_problem_stars: Dict[str, int] = {}
        if isinstance(stars_raw, dict):
            per_problem_stars = {
                str(k): max(0, min(3, _as_int(v)))
                for k, v in stars_raw.items()
            }

        state = cls(
            total_xp=_as_int(data.get("total_xp"), 0),
            solved=solved,
            current_streak=_as_int(data.get("current_streak"), 0),
            best_streak=_as_int(data.get("best_streak"), 0),
            hints_used=hints_used,
            per_problem_stars=per_problem_stars,
        )
        # Never trust a stored unlock level; derive it from solved problems.
        state._refresh_unlocked()
        state.best_streak = max(state.best_streak, state.current_streak)
        return state


# --------------------------------------------------------------------------- #
# Persistence (JSON, standard library only).
# --------------------------------------------------------------------------- #

def progress_dir() -> str:
    """Directory holding the save file: ``~/.automata_tutor``."""
    return os.path.join(os.path.expanduser("~"), ".automata_tutor")


def progress_path() -> str:
    """Full path to the save file: ``~/.automata_tutor/progress.json``."""
    return os.path.join(progress_dir(), "progress.json")


def load_progress() -> GameState:
    """Load the saved profile, or return a fresh one.

    A missing file, unreadable file, or corrupt/invalid JSON all result in a
    brand new :class:`GameState` rather than an exception -- the game should
    always start, even from a damaged save.
    """
    path = progress_path()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (FileNotFoundError, OSError, ValueError):
        return GameState()

    if not isinstance(data, dict):
        return GameState()

    try:
        return GameState.from_dict(data)
    except Exception:
        # Any unexpected shape -> start fresh rather than crash.
        return GameState()


def save_progress(state: GameState) -> None:
    """Persist ``state`` to :func:`progress_path`, creating the dir if needed.

    The write is atomic-ish: it goes to a temporary file in the same
    directory and is then renamed over the destination, so a crash mid-write
    cannot leave a half-written ``progress.json`` behind.
    """
    directory = progress_dir()
    os.makedirs(directory, exist_ok=True)

    final_path = progress_path()
    tmp_path = final_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(state.to_dict(), fh, indent=2, sort_keys=True)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp_path, final_path)


def reset_progress() -> GameState:
    """Delete any saved profile and return a fresh :class:`GameState`.

    Removing the file is best-effort: a missing file is fine, and a failure
    to delete is swallowed so the caller still gets a clean state.
    """
    try:
        os.remove(progress_path())
    except (FileNotFoundError, OSError):
        pass
    return GameState()
