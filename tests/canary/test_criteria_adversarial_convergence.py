"""Tests for tests/canary/criteria/adversarial_convergence.py (plan-006 §C9).

Coverage (≥3 tests per plan §Test deltas):

* PASS — every produced doc is ``status: Stable``.
* FAIL — one produced doc is ``status: Draft`` (and not override-eligible).
* PASS-with-override — APPROVED-WITH-DEBT doc is honored by an explicit
  ``--user-override <doc-id>:<reason>`` entry.

Plus regression tests:

* Empty ``produced_files`` + ``n_ok_dispatches >= 1`` ⇒ FAIL with
  iter-2-M3 defense-in-depth diagnostic.
* Empty ``produced_files`` + ``n_ok_dispatches == 0`` ⇒ vacuous PASS.
* APPROVED-WITH-DEBT without override ⇒ FAIL.
* Non-eligible status (Draft) cannot be saved by override ⇒ FAIL.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.canary.criteria import CriterionStatus
from tests.canary.criteria.adversarial_convergence import check


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


_KDOC_TEMPLATE = """---
kdoc_id: {doc_id}
status: {status}
topic: "test"
sources:
  - "[arXiv:9999.99999]"
created: 2026-04-26
last_reviewed: 2026-04-26
review_rounds: 0
superseded_by: null
---

# Knowledge: Test

Body.
"""


_ASSERTION_TEMPLATE = """---
assertion_id: {doc_id}
status: {status}
knowledge_doc_ids: [K-001-test]
upstream_ref_hash: "abc123"
---

# Assertion: Test

Body.
"""


def _write_kdoc(
    knowledge_dir: Path, doc_id: str, status: str
) -> Path:
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    path = knowledge_dir / f"{doc_id}.md"
    path.write_text(
        _KDOC_TEMPLATE.format(doc_id=doc_id, status=status), encoding="utf-8"
    )
    return path


def _write_assertion(
    assertion_dir: Path, doc_id: str, status: str
) -> Path:
    assertion_dir.mkdir(parents=True, exist_ok=True)
    path = assertion_dir / f"{doc_id}.md"
    path.write_text(
        _ASSERTION_TEMPLATE.format(doc_id=doc_id, status=status),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def sandbox(tmp_path: Path) -> tuple[Path, Path]:
    """Return ``(knowledge_dir, assertion_dir)`` under a fresh tmp_path."""
    return tmp_path / "knowledge", tmp_path / "assertions"


# ---------------------------------------------------------------------------
# Required tests (per task brief — ≥3)
# ---------------------------------------------------------------------------


def test_pass_all_stable(sandbox):
    """PASS — every produced doc has ``status: Stable``."""
    knowledge_dir, assertion_dir = sandbox
    k1 = _write_kdoc(knowledge_dir, "K-001-test", "Stable")
    k2 = _write_kdoc(knowledge_dir, "K-002-test", "Stable")
    a1 = _write_assertion(assertion_dir, "A-001-test", "Stable")

    result = check(
        produced_files=[k1, k2, a1],
        knowledge_dir=knowledge_dir,
        assertion_dir=assertion_dir,
        n_ok_dispatches=2,
    )

    assert result.status == CriterionStatus.PASS, result.summary
    assert result.passed is True
    assert "3/3" in result.summary
    assert result.payload["n_total"] == 3
    assert result.payload["n_pass"] == 3
    assert result.payload["n_overrides_honored"] == 0


def test_fail_one_draft(sandbox):
    """FAIL — one produced doc is ``status: Draft`` (not override-eligible)."""
    knowledge_dir, assertion_dir = sandbox
    k1 = _write_kdoc(knowledge_dir, "K-001-test", "Stable")
    k2 = _write_kdoc(knowledge_dir, "K-002-test", "Draft")
    a1 = _write_assertion(assertion_dir, "A-001-test", "Stable")

    result = check(
        produced_files=[k1, k2, a1],
        knowledge_dir=knowledge_dir,
        assertion_dir=assertion_dir,
        n_ok_dispatches=2,
    )

    assert result.status == CriterionStatus.FAIL
    assert result.passed is False
    fail_records = result.payload["fail_records"]
    assert len(fail_records) == 1
    assert fail_records[0]["doc_id"] == "K-002-test"
    assert fail_records[0]["status"] == "Draft"
    # Draft is NOT override-eligible.
    assert fail_records[0]["override_eligible"] is False


def test_pass_with_override(sandbox):
    """PASS-with-override — APPROVED-WITH-DEBT honored by --user-override."""
    knowledge_dir, assertion_dir = sandbox
    k1 = _write_kdoc(knowledge_dir, "K-001-test", "Stable")
    k2 = _write_kdoc(knowledge_dir, "K-002-test", "APPROVED-WITH-DEBT")
    a1 = _write_assertion(assertion_dir, "A-001-test", "Stable")

    result = check(
        produced_files=[k1, k2, a1],
        knowledge_dir=knowledge_dir,
        assertion_dir=assertion_dir,
        user_overrides=[
            "K-002-test:upstream paper has unresolved typo; see "
            "brief 002 §3.4"
        ],
        n_ok_dispatches=2,
    )

    assert result.status == CriterionStatus.PASS, result.summary
    assert result.passed is True
    assert result.payload["n_overrides_honored"] == 1
    honored = result.payload["honored_overrides"]
    assert "K-002-test" in honored
    assert (
        "unresolved typo"
        in honored["K-002-test"]["reason"]
    )
    # Override records are exposed for the canary report's
    # `## User overrides` markdown stanza (NOT a frontmatter field).
    records = result.payload["override_records"]
    assert len(records) == 1
    assert records[0]["status"] == "APPROVED-WITH-DEBT"


# ---------------------------------------------------------------------------
# Regression / edge-case tests
# ---------------------------------------------------------------------------


def test_iter2_m3_empty_produced_with_ok_dispatch_fails(sandbox):
    """iter-2-M3 defense-in-depth: empty produced_files + ≥1 ok ⇒ FAIL."""
    knowledge_dir, assertion_dir = sandbox

    result = check(
        produced_files=[],
        knowledge_dir=knowledge_dir,
        assertion_dir=assertion_dir,
        n_ok_dispatches=2,
    )

    assert result.status == CriterionStatus.FAIL
    # Diagnostic must cite the iter-2-S1 dispatcher-bug class.
    assert "iter-2-S1" in " ".join(result.details) or "iter-2-S1" in result.summary
    assert result.payload["fail_reason"] == "iter-2-M3-empty-produced-files"
    assert result.payload["n_ok_dispatches"] == 2


def test_empty_produced_no_ok_dispatch_is_vacuous_pass(sandbox):
    """Empty produced_files with no ok dispatches ⇒ vacuous PASS.

    This is the unit-fixture case where the dispatcher path was never
    exercised. The defense-in-depth gate only fires when there was at
    least one ok dispatch — we don't punish unit-test fixtures.
    """
    knowledge_dir, assertion_dir = sandbox

    result = check(
        produced_files=[],
        knowledge_dir=knowledge_dir,
        assertion_dir=assertion_dir,
        n_ok_dispatches=0,
    )

    assert result.status == CriterionStatus.PASS
    assert result.payload["n_total"] == 0


def test_approved_with_debt_without_override_fails(sandbox):
    """APPROVED-WITH-DEBT without explicit override ⇒ FAIL."""
    knowledge_dir, assertion_dir = sandbox
    k1 = _write_kdoc(knowledge_dir, "K-001-test", "APPROVED-WITH-DEBT")

    result = check(
        produced_files=[k1],
        knowledge_dir=knowledge_dir,
        assertion_dir=assertion_dir,
        user_overrides=None,
        n_ok_dispatches=1,
    )

    assert result.status == CriterionStatus.FAIL
    fail_records = result.payload["fail_records"]
    assert len(fail_records) == 1
    # The doc IS override-eligible — but no override was supplied.
    assert fail_records[0]["override_eligible"] is True


def test_draft_status_cannot_be_overridden(sandbox):
    """Override only applies to APPROVED-WITH-DEBT, never Draft."""
    knowledge_dir, assertion_dir = sandbox
    k1 = _write_kdoc(knowledge_dir, "K-001-test", "Draft")

    result = check(
        produced_files=[k1],
        knowledge_dir=knowledge_dir,
        assertion_dir=assertion_dir,
        user_overrides=["K-001-test:please ignore this draft"],
        n_ok_dispatches=1,
    )

    assert result.status == CriterionStatus.FAIL
    fail_records = result.payload["fail_records"]
    assert len(fail_records) == 1
    assert fail_records[0]["status"] == "Draft"
    assert fail_records[0]["override_eligible"] is False
    # No override should have been honored.
    assert result.payload["n_overrides_honored"] == 0
