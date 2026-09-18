"""Condition DSL evaluator (PLAN §6).

Grammar: tokens joined by `` and `` / `` or ``, an optional ``not `` prefix on a token, no parentheses;
``and`` binds tighter than ``or``. An unknown or malformed token raises :class:`ConditionError`.

Tokens
------
``evidence:<id>``        evidence examined
``known:<id>``           evidence known or examined
``revealed:<secret_id>`` secret revealed in a turn the player witnessed (any suspect's)
``stress>=N``            this suspect's stress >= N
``flatter_count>=N`` / ``threaten_count>=N``   tactic used on this suspect >= N times
``turn>=N``              game turn >= N
``searched:<location>``  location searched
``clock>=HH:MM``         clock at or past that time
"""
from __future__ import annotations

import re
from typing import Any

__all__ = ["ConditionError", "context_for", "evaluate", "parse", "parse_clock", "rule_holds"]


class ConditionError(ValueError):
    """Raised for an empty expression or an unknown / malformed token."""


_ID_TOKEN = re.compile(r"^(evidence|known|revealed|searched):([A-Za-z0-9_\-]+)$")
_NUM_TOKEN = re.compile(r"^(stress|flatter_count|threaten_count|turn)>=(\d+)$")
_CLOCK_TOKEN = re.compile(r"^clock>=(\d{1,2}):(\d{2})$")
_OR = re.compile(r"\s+or\s+")
_AND = re.compile(r"\s+and\s+")

# Parsed form: list of conjunctions; each conjunction is a list of (negated, token) pairs.
Parsed = list[list[tuple[bool, str]]]


def parse_clock(hhmm: str) -> int:
    """'HH:MM' -> minutes since midnight. Raises ConditionError on a bad value."""
    m = re.match(r"^(\d{1,2}):(\d{2})$", hhmm.strip())
    if not m:
        raise ConditionError(f"bad clock value {hhmm!r}")
    hours, minutes = int(m.group(1)), int(m.group(2))
    if hours > 23 or minutes > 59:
        raise ConditionError(f"bad clock value {hhmm!r}")
    return hours * 60 + minutes


def _check_token(token: str) -> None:
    if _ID_TOKEN.match(token) or _NUM_TOKEN.match(token):
        return
    m = _CLOCK_TOKEN.match(token)
    if m:
        parse_clock(f"{m.group(1)}:{m.group(2)}")
        return
    raise ConditionError(f"unknown condition token {token!r}")


def parse(expr: str) -> Parsed:
    """Validate and parse an expression without evaluating it."""
    if not isinstance(expr, str) or not expr.strip():
        raise ConditionError("empty condition")
    if "(" in expr or ")" in expr:
        raise ConditionError("parentheses are not allowed in conditions")
    parsed: Parsed = []
    for disjunct in _OR.split(expr.strip()):
        conj: list[tuple[bool, str]] = []
        for term in _AND.split(disjunct.strip()):
            term = term.strip()
            if not term:
                raise ConditionError(f"empty term in {expr!r}")
            negated = False
            if term.startswith("not "):
                negated = True
                term = term[4:].strip()
                if not term:
                    raise ConditionError(f"dangling 'not' in {expr!r}")
            if " " in term:
                raise ConditionError(f"unknown condition token {term!r}")
            _check_token(term)
            conj.append((negated, term))
        parsed.append(conj)
    return parsed


def _eval_token(token: str, ctx: dict[str, Any]) -> bool:
    m = _ID_TOKEN.match(token)
    if m:
        kind, ident = m.group(1), m.group(2)
        if kind == "evidence":
            return ident in ctx.get("examined", set())
        if kind == "known":
            return ident in ctx.get("known", set()) or ident in ctx.get("examined", set())
        if kind == "revealed":
            return ident in ctx.get("revealed", set())
        if kind == "searched":
            return ident in ctx.get("searched", set())
    m = _NUM_TOKEN.match(token)
    if m:
        field, n = m.group(1), int(m.group(2))
        return int(ctx.get(field, 0) or 0) >= n
    m = _CLOCK_TOKEN.match(token)
    if m:
        return int(ctx.get("clock_minutes", 0) or 0) >= parse_clock(f"{m.group(1)}:{m.group(2)}")
    raise ConditionError(f"unknown condition token {token!r}")


def evaluate(expr: str, ctx: dict[str, Any]) -> bool:
    """Evaluate ``expr`` against ``ctx`` (see :func:`context_for` for the ctx keys)."""
    for conj in parse(expr):
        if all((not _eval_token(tok, ctx)) if neg else _eval_token(tok, ctx) for neg, tok in conj):
            return True
    return False


def context_for(case: dict, world: dict, suspect_id: str) -> dict[str, Any]:
    """Build the evaluation context for one suspect from the world state."""
    evidence = world.get("evidence", {})
    examined = {eid for eid, st in evidence.items() if st.get("state") == "examined"}
    known = {eid for eid, st in evidence.items() if st.get("state") in ("known", "examined")}
    revealed: set[str] = set()
    for st in world.get("suspects", {}).values():
        revealed.update(st.get("revealed_secret_ids", []))
    game = world.get("game", {})
    state = world.get("suspects", {}).get(suspect_id, {})
    return {
        "examined": examined,
        "known": known,
        "revealed": revealed,
        "stress": int(state.get("stress", 0)),
        "flatter_count": int(state.get("flatter_count", 0)),
        "threaten_count": int(state.get("threaten_count", 0)),
        "turn": int(game.get("turn", 0)),
        "searched": set(game.get("searched_locations", [])),
        "clock_minutes": int(game.get("clock_minutes", 0)),
    }


def rule_holds(rule: dict | None, ctx: dict[str, Any]) -> bool:
    """A ``special_unlocks`` entry: requires_any / requires_all / requires_revealed. ``None`` holds."""
    if not rule:
        return True
    any_conds = rule.get("requires_any") or []
    if any_conds and not any(evaluate(c, ctx) for c in any_conds):
        return False
    all_conds = rule.get("requires_all") or []
    if all_conds and not all(evaluate(c, ctx) for c in all_conds):
        return False
    revealed = ctx.get("revealed", set())
    for sid in rule.get("requires_revealed") or []:
        if sid not in revealed:
            return False
    return True
