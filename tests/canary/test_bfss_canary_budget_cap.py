"""CI-gating tests for the BFSS canary budget-cap enforcement.

These tests run in the default CI suite (no @pytest.mark.canary skip).
They verify that :class:`BudgetTracker` raises :class:`BudgetExceeded`
correctly and that the canary orchestrator writes a partial report and
exits when ``non_interactive=True`` and the cap is breached.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Allow direct import of budget_tracker from the same canary package.
_CANARY_DIR = Path(__file__).resolve().parent
if str(_CANARY_DIR) not in sys.path:
    sys.path.insert(0, str(_CANARY_DIR))

from budget_tracker import BudgetExceeded, BudgetTracker  # noqa: E402


# ---------------------------------------------------------------------------
# Unit tests for BudgetTracker
# ---------------------------------------------------------------------------


def test_budget_tracker_raises_on_exceeded() -> None:
    """record(201) on a cap-200 tracker must raise BudgetExceeded."""
    tracker = BudgetTracker(estimate=100, multiplier=2.0)
    # cap = 100 * 2.0 = 200
    with pytest.raises(BudgetExceeded):
        tracker.record(201)


def test_budget_tracker_ok_at_cap() -> None:
    """record(200) exactly at the cap must NOT raise."""
    tracker = BudgetTracker(estimate=100, multiplier=2.0)
    # cap = 200; recording exactly 200 should be fine
    tracker.record(200)  # should not raise
    assert tracker.used == 200


# ---------------------------------------------------------------------------
# Integration test: budget cap triggers partial report + SystemExit
# ---------------------------------------------------------------------------


def test_bfss_canary_budget_cap_triggers_user_ack(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A canary run that exceeds budget in non-interactive mode must SystemExit(1)
    OR write a canary-report-partial-*.md file to the output directory.

    Uses a tiny estimate_tokens=1 (cap = 3 tokens) so the first paper's
    fake 100-token cost immediately blows the cap.  monkeypatch redirects
    the partial-report write to tmp_path.
    """
    import importlib
    import types

    # We need to import run-bfss-canary as a module.  Its filename contains
    # a hyphen so we use importlib machinery.
    script_path = _CANARY_DIR / "run-bfss-canary.py"
    spec = importlib.util.spec_from_file_location("run_bfss_canary", script_path)
    assert spec is not None and spec.loader is not None
    canary_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(canary_mod)  # type: ignore[union-attr]

    # Patch _DRY_RUN_TOKEN_COST to something large to guarantee cap breach.
    monkeypatch.setattr(canary_mod, "_DRY_RUN_TOKEN_COST", 10)

    # Patch _PER_PAPER_TOKEN_ESTIMATE to 1 so cap = 1 * 3 = 3 tokens.
    monkeypatch.setattr(canary_mod, "_PER_PAPER_TOKEN_ESTIMATE", 1)

    # Redirect partial-report writes to tmp_path by patching manifest parent.
    manifest_path = _CANARY_DIR / "bfss-corpus-manifest.json"

    # Redirect the partial report directory to tmp_path by monkey-patching
    # the manifest_path used inside run_canary.
    import json
    with manifest_path.open() as fh:
        manifest_data = json.load(fh)

    # Create a fake manifest in tmp_path with a non-existent refs_dir.
    # run_canary with dry_run=True skips integrity check so refs_dir is irrelevant.
    fake_manifest = tmp_path / "bfss-corpus-manifest.json"
    manifest_data["references_dir"] = str(tmp_path / "refs")
    fake_manifest.write_text(json.dumps(manifest_data), encoding="utf-8")

    # In non-interactive mode, the function should call sys.exit(1).
    with pytest.raises(SystemExit) as exc_info:
        canary_mod.run_canary(
            refs_dir=tmp_path / "refs",
            manifest_path=fake_manifest,
            dry_run=True,
            non_interactive=True,
            budget_multiplier=3.0,
        )

    # Accept either exit code 1, or that a partial report file was written.
    partial_files = list(tmp_path.glob("canary-report-partial-*.md"))
    exited_with_1 = exc_info.value.code == 1

    assert exited_with_1 or partial_files, (
        "Expected SystemExit(1) or a partial report file in tmp_path; "
        f"got exit code {exc_info.value.code} and no partial files."
    )


# ---------------------------------------------------------------------------
# Anchor test: per-paper estimate pinned to plan-006 §C11 smoke evidence
# ---------------------------------------------------------------------------


def test_per_paper_estimate_anchored_to_plan_006_smoke() -> None:
    """``_PER_PAPER_TOKEN_ESTIMATE`` must equal 1_200_000 per plan-006 §C11.

    The constant is anchored to the K-001 plan-005 smoke run, which
    established that a realistic per-paper digest cost (with .tex
    sources + 2–3 adversarial rounds) lands in the ~700k–1.2M token
    band.  Plan-006 §C11 fixes the canary's per-paper estimate at the
    1.2M high-end of that band so the 16-paper × 3× multiplier cap
    (57.6M tokens, ≈ $173 worst-case input at Sonnet 4.6 list
    pricing) does not falsely abort a live canary run.

    If this test fails, either the constant has drifted (revert or
    update plan-006 §C11) or the smoke evidence has been superseded
    by a fresh measurement (in which case update both the constant
    and this anchor test together, and cite the new evidence).
    """
    import importlib.util

    script_path = _CANARY_DIR / "run-bfss-canary.py"
    spec = importlib.util.spec_from_file_location("run_bfss_canary", script_path)
    assert spec is not None and spec.loader is not None
    canary_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(canary_mod)  # type: ignore[union-attr]

    assert canary_mod._PER_PAPER_TOKEN_ESTIMATE == 1_200_000, (
        "plan-006 §C11 pins _PER_PAPER_TOKEN_ESTIMATE at 1_200_000 "
        "(anchored to K-001 plan-005 smoke); got "
        f"{canary_mod._PER_PAPER_TOKEN_ESTIMATE}."
    )
