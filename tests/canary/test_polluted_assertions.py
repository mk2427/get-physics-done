from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_polluted_assertions_not_in_live_tree() -> None:
    prefixes = json.loads(
        (_FIXTURES / "polluted-assertion-prefixes.json").read_text(encoding="utf-8")
    )
    assertion_dir = _ROOT / "GPD" / "assertions"
    offenders = []
    for prefix in prefixes:
        offenders.extend(path.name for path in assertion_dir.glob(f"{prefix}-*.md"))
    assert offenders == []


def test_polluted_reviews_not_in_live_tree() -> None:
    prefixes = json.loads(
        (_FIXTURES / "polluted-assertion-prefixes.json").read_text(encoding="utf-8")
    )
    review_dir = _ROOT / "GPD" / "reviews"
    offenders = []
    for prefix in prefixes:
        offenders.extend(path.name for path in review_dir.glob(f"{prefix}-*"))
    assert offenders == []


def test_a001_a002_provenance_decision_is_recorded() -> None:
    data = json.loads(
        (_FIXTURES / "retained-assertion-provenance.json").read_text(encoding="utf-8")
    )
    for key in ("A-001", "A-002"):
        record = data[key]
        path = _ROOT / record["path"]
        assert record["decision"] in {"retained", "deleted"}
        assert record["reason"]
        if record["decision"] == "retained":
            assert path.exists()
