"""Budget tracking utilities for the BFSS canary orchestrator.

Shared by ``run-bfss-canary.py`` (script) and
``test_bfss_canary_budget_cap.py`` (pytest).  Kept small and import-free
beyond the stdlib so the test suite can always import it.
"""

from __future__ import annotations


class BudgetExceeded(Exception):
    """Raised by :class:`BudgetTracker` when the token cap is breached."""


class BudgetTracker:
    """Track cumulative token usage against an estimate-based cap.

    Parameters
    ----------
    estimate_tokens:
        Best-guess total token cost for the canary run (sum of per-paper
        estimates).
    multiplier:
        Safety factor applied to *estimate_tokens* to derive the hard cap.
        Default 3.0 (i.e. cap = estimate × 3).
    """

    def __init__(self, estimate_tokens: int = 0, multiplier: float = 3.0, *, estimate: int | None = None) -> None:
        # Accept either ``estimate_tokens=`` (primary) or ``estimate=`` (briefing alias).
        if estimate is not None:
            estimate_tokens = estimate
        self.estimate: int = estimate_tokens
        self.cap: float = estimate_tokens * multiplier
        self.used: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(self, tokens: int) -> None:
        """Add *tokens* to the running total; raise :class:`BudgetExceeded` if over cap.

        Parameters
        ----------
        tokens:
            Number of tokens consumed by the most recent skill invocation.

        Raises
        ------
        BudgetExceeded
            When ``self.used`` after adding *tokens* exceeds ``self.cap``.
        """
        self.used += tokens
        if self.used > self.cap:
            raise BudgetExceeded(
                f"Token budget exceeded: used {self.used} > cap {self.cap:.0f} "
                f"(estimate={self.estimate}, multiplier={self.cap / self.estimate:.1f}x)"
            )

    def fraction_used(self) -> float:
        """Return fraction of cap consumed (0.0–1.0+).

        Returns 0.0 when cap is zero to avoid division-by-zero.
        """
        return self.used / self.cap if self.cap > 0 else 0.0

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"BudgetTracker(used={self.used}, cap={self.cap:.0f}, "
            f"estimate={self.estimate}, pct={self.fraction_used():.1%})"
        )
