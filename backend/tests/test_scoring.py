"""Accusation scoring (PLAN §8.9)."""
from app.engine import scoring


def test_score_correct_murderer_and_method(case):
    s = scoring.score(case, "pell", ["cyanide_jar"], 0)
    assert s == {"murderer": 60, "method": 20, "motive": 0, "total": 80}
    assert scoring.rank(s["total"]) == "Detective"


def test_score_full_marks(case):
    s = scoring.score(case, "pell", ["decanter", "necklace_clasp"], 20)
    assert s["total"] == 100
    assert scoring.rank(100) == "Inspector"


def test_score_wrong_suspect(case):
    s = scoring.score(case, "margaret", ["cyanide_jar"], 10)
    assert s["murderer"] == 0 and s["method"] == 20 and s["motive"] == 10 and s["total"] == 30
    assert scoring.rank(30) == "Rookie"


def test_method_needs_overlap(case):
    assert scoring.score(case, "pell", ["ledger", "cigar_case"], 0)["method"] == 0
    assert scoring.score(case, "pell", [], 0)["method"] == 0


def test_motive_points_snap_to_allowed(case):
    assert scoring.score(case, "pell", [], 13)["motive"] == 10
    assert scoring.score(case, "pell", [], 99)["motive"] == 20
    assert scoring.score(case, "pell", [], -5)["motive"] == 0
    assert scoring.score(case, "pell", [], None)["motive"] == 0


def test_rank_boundaries():
    assert scoring.rank(90) == "Inspector"
    assert scoring.rank(89) == "Detective"
    assert scoring.rank(60) == "Detective"
    assert scoring.rank(59) == "Rookie"


def test_confidence_badge():
    assert scoring.confidence_badge(0.8) == "bold call"
    assert scoring.confidence_badge(0.95) == "bold call"
    assert scoring.confidence_badge(0.3) == "hedged"
    assert scoring.confidence_badge(0.1) == "hedged"
    assert scoring.confidence_badge(0.5) is None
    assert scoring.confidence_badge("x") is None
