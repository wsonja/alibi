"""Case Consistency Checker (PLAN §7.6).

* ``static_check(case) -> list[str]`` — pure code, a faithful port of ``scripts/validate_case.py`` (same rules, same
  messages, including proof-path satisfiability).  Used by case loading in every mode.
* ``llm_check(case, progress_cb)`` — Gemini only: a solver must name ``solution.murderer`` from all evidence and all
  secrets; then the strongest alternative theory is argued and graded ``implausible``.
* ``run_author_with_checks(...)`` — writes a case, checks it, re-runs the Author with the notes (max 3 rounds).
"""

from __future__ import annotations

import inspect
import json
import logging
import re
from collections.abc import Callable
from typing import Any

from . import client as llm
from .tools import ALTERNATIVE_CASE, GRADE_ALTERNATIVE, SOLVE_CASE

log = logging.getLogger("alibi.agents.checker")

TACTICS = {"evidence", "threaten", "flatter", "bluff", "silence"}
TOKEN = re.compile(
    r"^(evidence:\w+|known:\w+|revealed:\w+|stress>=\d+|flatter_count>=\d+|threaten_count>=\d+|turn>=\d+|searched:\w+|clock>=\d\d:\d\d)$"
)
SUSPECT_REQUIRED = [
    "id", "name", "role", "public_description", "persona", "speech_quirk", "portrait_prompt", "personality", "goals",
    "knowledge", "secrets", "stress_sensitivity", "crack_thresholds", "special_unlocks", "shutdown_rules",
    "deflections", "framing_actions", "tells", "guilty", "relationships",
]
EVIDENCE_REQUIRED = ("id", "name", "location", "initially_known", "description", "examined_detail", "points_to")
TOP_REQUIRED = ("suspects", "evidence", "locations", "solution")


def _as_list(x: Any) -> list:
    return x if isinstance(x, list) else []


def _as_dict(x: Any) -> dict:
    return x if isinstance(x, dict) else {}


def static_check(case: dict) -> list[str]:
    """Return every rule violation as a message (empty list = valid). Same rules/messages as scripts/validate_case.py."""
    errs: list[str] = []
    if not isinstance(case, dict):
        return ["case is not a JSON object"]
    for k in TOP_REQUIRED:
        if k not in case:
            errs.append(f"missing top-level key {k}")
    if errs:
        return errs

    suspects_raw = [s for s in _as_list(case.get("suspects")) if isinstance(s, dict) and s.get("id")]
    sus = {s["id"]: s for s in suspects_raw}
    if len(sus) != len(_as_list(case.get("suspects"))):
        errs.append("every suspect needs a unique id")
    evidence_items = [e for e in _as_list(case.get("evidence")) if isinstance(e, dict) and e.get("id")]
    dynamic_items = [e for e in _as_list(case.get("dynamic_evidence")) if isinstance(e, dict) and e.get("id")]
    ev = {e["id"] for e in evidence_items} | {e["id"] for e in dynamic_items}
    locations = [loc for loc in _as_list(case.get("locations")) if isinstance(loc, dict) and loc.get("id")]
    loc = {loc["id"] for loc in locations}
    sec: dict[str, str] = {}
    for sid, s in sus.items():
        for x in _as_list(s.get("secrets")):
            if isinstance(x, dict) and x.get("id"):
                if x["id"] in sec:
                    errs.append(f"{sid}/{x['id']}: duplicate secret id")
                sec[x["id"]] = sid

    def check_cond(expr: Any, ctx: str) -> None:
        if not isinstance(expr, str) or not expr.strip():
            errs.append(f"{ctx}: bad token {expr!r}")
            return
        for part in re.split(r"\s+(?:and|or)\s+", expr.strip()):
            tok = part.removeprefix("not ")
            if not TOKEN.match(tok):
                errs.append(f"{ctx}: bad token {tok!r}")
            kind, _, val = tok.partition(":")
            if kind == "evidence" or kind == "known":
                if val not in ev:
                    errs.append(f"{ctx}: unknown evidence {val}")
            elif kind == "revealed":
                if val not in sec:
                    errs.append(f"{ctx}: unknown secret {val}")
            elif kind == "searched" and val not in loc:
                errs.append(f"{ctx}: unknown location {val}")

    # locations <-> evidence
    for location in locations:
        for eid in _as_list(location.get("evidence_ids")):
            if eid not in ev:
                errs.append(f"location {location['id']}: unknown evidence {eid}")
    for e in evidence_items + dynamic_items:
        if e.get("location") not in loc:
            errs.append(f"evidence {e['id']}: unknown location")
        for k in EVIDENCE_REQUIRED:
            if k not in e:
                errs.append(f"evidence {e['id']}: missing {k}")
    listed = {eid for location in locations for eid in _as_list(location.get("evidence_ids"))}
    for e in evidence_items:
        if e["id"] not in listed:
            errs.append(f"evidence {e['id']} not listed under any location")

    # suspects
    guilty = [s for s in sus.values() if s.get("guilty")]
    if len(guilty) != 1:
        errs.append(f"expected exactly one guilty, got {len(guilty)}")
    for sid, s in sus.items():
        for k in SUSPECT_REQUIRED:
            if k not in s:
                errs.append(f"{sid}: missing {k}")
        sens = _as_dict(s.get("stress_sensitivity"))
        if set(sens) != TACTICS:
            errs.append(f"{sid}: sensitivity keys {set(sens)}")
        thresholds = _as_list(s.get("crack_thresholds"))
        if len(thresholds) != 3 or thresholds != sorted(thresholds):
            errs.append(f"{sid}: thresholds")
        secrets = [x for x in _as_list(s.get("secrets")) if isinstance(x, dict)]
        tiers = sorted(x.get("tier", 0) for x in secrets)
        if tiers != [1, 2, 3]:
            errs.append(f"{sid}: secret tiers {tiers}")
        for x in secrets:
            xid = x.get("id", "?")
            if "key_phrases" not in x:
                errs.append(f"{sid}/{xid}: no key_phrases")
            else:
                try:
                    re.compile(x["key_phrases"])
                except (re.error, TypeError) as exc:
                    errs.append(f"{sid}/{xid}: bad key_phrases regex ({exc})")
            if not str(x.get("text") or "").strip():
                errs.append(f"{sid}/{xid}: empty text")
        for secid, rule in _as_dict(s.get("special_unlocks")).items():
            if sec.get(secid) != sid:
                errs.append(f"{sid}: special_unlocks for foreign/unknown secret {secid}")
            rule = _as_dict(rule)
            for c in _as_list(rule.get("requires_any")) + _as_list(rule.get("requires_all")):
                check_cond(c, f"{sid}/{secid}")
            for r in _as_list(rule.get("requires_revealed")):
                if r not in sec:
                    errs.append(f"{sid}/{secid}: requires_revealed unknown {r}")
        for t in _as_dict(s.get("shutdown_rules")):
            if t not in TACTICS:
                errs.append(f"{sid}: shutdown tactic {t}")
        for fa in _as_list(s.get("framing_actions")):
            if not isinstance(fa, dict):
                errs.append(f"{sid}: framing action is not an object")
                continue
            fid = fa.get("id", "?")
            check_cond(fa.get("trigger"), f"{sid}/{fid}")
            eff = _as_dict(fa.get("effect"))
            if "remove_evidence" in eff and eff["remove_evidence"] not in ev:
                errs.append(f"{sid}/{fid}: remove unknown")
            if "add_evidence_id" in eff and eff["add_evidence_id"] not in {e["id"] for e in dynamic_items}:
                errs.append(f"{sid}/{fid}: add not dynamic")
        rels = _as_dict(s.get("relationships"))
        for other, rel in rels.items():
            if other not in sus or other == sid:
                errs.append(f"{sid}: relationship {other}")
            try:
                trust = float(_as_dict(rel).get("trust"))
            except (TypeError, ValueError):
                trust = -1.0
            if not 0 <= trust <= 1:
                errs.append(f"{sid}: trust {other}")
        if set(rels) != set(sus) - {sid}:
            errs.append(f"{sid}: relationships incomplete")
        if set(_as_dict(s.get("tells"))) != {"nervous", "angry", "cracking"}:
            errs.append(f"{sid}: tells")
        if not _as_list(s.get("deflections")):
            errs.append(f"{sid}: no deflections")
        if s.get("guilty"):
            conf = [x for x in secrets if x.get("is_confession")]
            if len(conf) != 1 or conf[0].get("tier") != 3:
                errs.append(f"{sid}: confession secret")
            rule = _as_dict(_as_dict(s.get("special_unlocks")).get(conf[0].get("id"), {})) if conf else {}
            if not any(
                isinstance(c, str) and c.startswith("evidence:")
                for c in _as_list(rule.get("requires_any")) + _as_list(rule.get("requires_all"))
            ):
                errs.append(f"{sid}: confession must require physical evidence")

    # solution
    sol = _as_dict(case.get("solution"))
    murderer = sol.get("murderer")
    if murderer not in sus or not sus[murderer].get("guilty"):
        errs.append("solution.murderer mismatch")
    for k in ("method_evidence_ids", "motive_evidence_ids"):
        for eid in _as_list(sol.get(k)):
            if eid not in ev:
                errs.append(f"solution.{k}: unknown {eid}")
    proof_paths = [p for p in _as_list(sol.get("proof_paths")) if isinstance(p, list)]
    if len(proof_paths) < 2:
        errs.append("need >=2 proof paths")
    for i, path in enumerate(proof_paths):
        for tok in path:
            check_cond(tok, f"proof_path[{i}]")

    # proof-path satisfiability: simulate unlocking with unlimited stress but honoring special_unlocks
    def satisfiable(path: list) -> str | None:
        examined: set[str] = set()
        revealed: set[str] = set()

        def holds(c: str) -> bool:
            neg = c.startswith("not ")
            c = c[4:] if neg else c
            k, _, v = c.partition(":")
            if k == "evidence":
                r = v in examined
            elif k == "revealed":
                r = v in revealed
            elif c.startswith(("stress>=", "flatter_count>=", "turn>=")):
                r = True
            else:
                r = False
            return (not r) if neg else r

        for tok in path:
            if not isinstance(tok, str):
                return f"{tok!r} not unlockable at that point"
            k, _, v = tok.partition(":")
            if k == "evidence":
                examined.add(v)
                continue
            if v not in sec:
                return f"{tok} not unlockable at that point"
            owner = sus[sec[v]]
            rule = _as_dict(_as_dict(owner.get("special_unlocks")).get(v, {}))
            ok = (
                (not rule.get("requires_any") or any(holds(c) for c in rule["requires_any"] if isinstance(c, str)))
                and all(holds(c) for c in _as_list(rule.get("requires_all")) if isinstance(c, str))
                and all(r in revealed for r in _as_list(rule.get("requires_revealed")))
            )
            if not ok:
                return f"{tok} not unlockable at that point"
            revealed.add(v)
        return None

    for i, path in enumerate(proof_paths):
        r = satisfiable(path)
        if r:
            errs.append(f"proof_path[{i}]: {r}")

    for rs in _as_list(case.get("rumor_seeds")):
        rs = _as_dict(rs)
        if rs.get("holder") not in sus:
            errs.append("rumor holder")
        for t in _as_list(rs.get("spreads_to")):
            if t not in sus:
                errs.append("rumor target")
    return errs


# --------------------------------------------------------------------------------------------------------------------
# LLM checks
# --------------------------------------------------------------------------------------------------------------------

ProgressCb = Callable[[str], Any] | None


async def _progress(cb: ProgressCb, line: str) -> None:
    log.info("checker: %s", line)
    if cb is None:
        return
    try:
        result = cb(line)
        if inspect.isawaitable(result):
            await result
    except Exception as exc:  # noqa: BLE001 - a broken progress sink must not break the pipeline
        log.debug("progress callback failed: %s", exc)


def dossier(case: dict, *, include_solution: bool = False) -> str:
    """Everything a solver may see: all evidence details and all secrets (never the solution unless asked)."""
    victim = _as_dict(case.get("victim"))
    lines = [
        f"Title: {case.get('title', '')}",
        f"Setting: {case.get('setting', '')}",
        f"Briefing: {case.get('briefing', '')}",
        f"Victim: {victim.get('name', '')} — {victim.get('description', '')}",
        f"Public cause of death: {victim.get('cause_of_death_public', '')}",
        "",
        "Public timeline:",
    ]
    lines += [f"- {t.get('time', '')}: {t.get('event', '')}" for t in _as_list(case.get("timeline_public")) if isinstance(t, dict)]
    lines += ["", "Locations:"]
    lines += [f"- {loc.get('id')}: {loc.get('name')} — {loc.get('description', '')}" for loc in _as_list(case.get("locations")) if isinstance(loc, dict)]
    lines += ["", "Evidence (with examined details):"]
    for e in _as_list(case.get("evidence")) + _as_list(case.get("dynamic_evidence")):
        if isinstance(e, dict):
            lines.append(f"- {e.get('id')} ({e.get('name')}, in {e.get('location')}): {e.get('description', '')} Examined: {e.get('examined_detail', '')}")
    lines += ["", "Suspects and ALL of their secrets:"]
    for s in _as_list(case.get("suspects")):
        if not isinstance(s, dict):
            continue
        lines.append(f"- {s.get('id')}: {s.get('name')}, {s.get('role')}. Public: {s.get('public_description', '')}")
        for x in _as_list(s.get("secrets")):
            if isinstance(x, dict):
                lines.append(f"    secret {x.get('id')} (tier {x.get('tier')}): {x.get('text', '')}")
    if include_solution:
        sol = _as_dict(case.get("solution"))
        lines += ["", f"Intended solution: murderer={sol.get('murderer')}; method={sol.get('method', '')}; motive={sol.get('motive', '')}"]
    return "\n".join(lines)


async def llm_check(case: dict, progress_cb: ProgressCb = None) -> dict:
    """Solve + alternative + grade. Returns a report dict with ``ok`` and ``notes`` for the Author."""
    report: dict[str, Any] = {"ok": False, "static_errors": [], "solve": None, "alternative": None, "grade": None, "notes": [], "lines": []}

    async def say(line: str) -> None:
        report["lines"].append(line)
        await _progress(progress_cb, line)

    static_errors = static_check(case)
    report["static_errors"] = static_errors
    if static_errors:
        await say(f"Checker: {len(static_errors)} structural problem(s) found.")
        report["notes"] = [f"Structural error: {e}" for e in static_errors]
        return report
    await say("Checker: structure and proof paths are sound.")
    if not llm.credential_available():
        raise llm.NotConfigured("The consistency checker needs a Gemini credential (GEMINI_API_KEY).")

    sol = _as_dict(case.get("solution"))
    murderer = str(sol.get("murderer"))
    suspect_ids = [s.get("id") for s in _as_list(case.get("suspects")) if isinstance(s, dict)]
    text = dossier(case)

    await say("Checker: asking a fresh detective to solve the case from all the evidence and secrets…")
    solve = await llm.call_tool(
        "author",
        "You are an expert detective. From the complete dossier (every piece of evidence with its examined detail, and "
        "every character's secrets) name the murderer by suspect id and explain your reasoning in a short paragraph. "
        f"Valid suspect ids: {', '.join(map(str, suspect_ids))}.",
        [{"role": "user", "content": text}],
        SOLVE_CASE,
        max_tokens=4000,
        temperature=0.2,
    )
    solve_ok = str(solve.get("murderer", "")).strip() == murderer
    report["solve"] = {"murderer": str(solve.get("murderer", "")), "reasoning": str(solve.get("reasoning", "")), "ok": solve_ok}
    if solve_ok:
        await say(f"Checker: the solver named {murderer} — correct.")
    else:
        await say(f"Checker: the solver named {solve.get('murderer')} instead of {murderer} — the evidence does not point clearly enough.")
        report["notes"].append(
            f"A careful solver given every clue and every secret concluded the murderer was '{solve.get('murderer')}', not "
            f"'{murderer}'. Reasoning: {solve.get('reasoning', '')} Make the evidence and secrets point unambiguously at {murderer}."
        )
        return report

    await say("Checker: arguing the strongest case for someone else…")
    alt = await llm.call_tool(
        "author",
        "You are a defence barrister. Using ONLY the dossier, argue the strongest possible case that a suspect OTHER than "
        f"'{murderer}' committed the murder. Pick the most plausible alternative suspect id from: "
        f"{', '.join(i for i in map(str, suspect_ids) if i != murderer)}. Be concrete: cite evidence and secrets.",
        [{"role": "user", "content": text}],
        ALTERNATIVE_CASE,
        max_tokens=4000,
        temperature=0.7,
    )
    report["alternative"] = {"suspect": str(alt.get("suspect", "")), "argument": str(alt.get("argument", ""))}
    await say(f"Checker: the alternative theory accuses {alt.get('suspect')}. Grading it…")
    grade = await llm.call_tool(
        "author",
        "You are the judge of a murder-mystery consistency check. Given the full dossier, the intended solution and an "
        "alternative theory, decide whether the alternative theory is genuinely plausible — i.e. the evidence and "
        "secrets in the dossier do NOT rule it out and a fair reader could reasonably reach it — or implausible "
        "because the dossier contradicts it or the intended murderer is clearly better supported. Give one sentence.",
        [
            {
                "role": "user",
                "content": dossier(case, include_solution=True)
                + f"\n\nAlternative theory (accuses {alt.get('suspect')}):\n{alt.get('argument', '')}",
            }
        ],
        GRADE_ALTERNATIVE,
        max_tokens=2000,
        temperature=0.0,
    )
    verdict = str(grade.get("verdict", "")).strip().lower()
    report["grade"] = {"verdict": verdict, "reason": str(grade.get("reason", ""))}
    if verdict == "implausible":
        await say("Checker: the alternative is implausible — the case holds up.")
        report["ok"] = True
    else:
        await say(f"Checker: the alternative against {alt.get('suspect')} is plausible — the case is rejected.")
        report["notes"].append(
            f"A plausible alternative theory accuses '{alt.get('suspect')}': {alt.get('argument', '')} Judge's reason: "
            f"{grade.get('reason', '')} Add or sharpen evidence so this alternative is clearly ruled out."
        )
    return report


async def run_author_with_checks(
    setting: str,
    n_suspects: int,
    difficulty: str,
    progress_cb: ProgressCb = None,
    max_rounds: int = 3,
) -> tuple[dict | None, dict]:
    """Author -> static check -> LLM check, re-running the Author with the notes. Returns (case, report)."""
    from . import author

    notes: list[str] = []
    case: dict | None = None
    report: dict = {"ok": False, "static_errors": [], "solve": None, "alternative": None, "grade": None, "notes": [], "lines": [], "rounds": 0}
    for round_no in range(1, max_rounds + 1):
        await _progress(progress_cb, f"Author: round {round_no} of {max_rounds}…")
        try:
            case = await author.write_case(setting, n_suspects, difficulty, progress_cb, notes=notes)
        except llm.InvalidOutput as exc:
            await _progress(progress_cb, f"Author: the draft was not valid JSON ({exc}); trying again.")
            notes = ["The previous draft was not a valid JSON case document. Return only the JSON object."]
            report = {**report, "rounds": round_no, "notes": notes}
            continue
        report = await llm_check(case, progress_cb)
        report["rounds"] = round_no
        if report["ok"]:
            await _progress(progress_cb, "Checker: case accepted.")
            return case, report
        notes = list(report["notes"])
        await _progress(progress_cb, f"Checker: {len(notes)} note(s) sent back to the Author.")
    await _progress(progress_cb, "Checker: no round produced an accepted case.")
    return case, report


def report_lines(report: dict) -> list[str]:
    """Human-readable lines for the New Case loading screen."""
    return [str(line) for line in (report or {}).get("lines", [])]


__all__ = ["dossier", "llm_check", "report_lines", "run_author_with_checks", "static_check"]


if __name__ == "__main__":  # pragma: no cover - convenience: python -m app.agents.checker path/to/case.json
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "app/cases/vane_hall.json"
    with open(path, encoding="utf-8") as fh:
        errors = static_check(json.load(fh))
    print("OK — no errors" if not errors else "ERRORS:")
    for e in errors:
        print(" -", e)
    sys.exit(1 if errors else 0)
