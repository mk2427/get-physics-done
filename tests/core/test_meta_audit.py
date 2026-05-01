"""Tests for gpd.core.meta_audit.

Brief 002 §Commit 6 required tests:

1. ``test_canonical_signature_grouping`` — fixture cluster-report rows with
   equivalent equations group to the same sha256 signature; inequivalent
   equations do NOT collide.
2. ``test_topic_keyword_grouping`` — keyword match on the controlled-vocab
   seed buckets rows by lowercase substring match; distinct topics
   separate into distinct buckets.
3. ``test_residual_row_to_candidate_axes`` — ungrouped rows appended to
   ``candidate-axes.md`` preserve the queue format and are append-only.

Plus the meta-audit schema validation assertion (brief 002 §Commit 6
acceptance criterion): ``templates/meta-audit-schema.md`` MUST validate
against the BFSS hand-built fixture ``cross-cluster-meta-audit.md`` §§1–8
structure, so the schema cannot drift away from a known-good emit shape.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from gpd.core.meta_audit import (
    CANDIDATE_AXES_HEADER,
    append_to_candidate_axes,
    canonical_signature,
    topic_keyword_group,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_PATH = _REPO_ROOT / "src" / "gpd" / "specs" / "templates" / "meta-audit-schema.md"


# --- (1) canonical-signature grouping ---------------------------------------


class TestCanonicalSignatureGrouping:
    """Brief 002 §Commit 6 Test 1."""

    def test_equivalent_equations_group_to_same_signature(self) -> None:
        """Two cluster-report rows quoting the SAME equation under different
        LaTeX surface forms (spacing, ``\\dfrac`` vs ``\\frac``, bare vs
        parenthesized fractions) MUST hash to identical canonical signatures.
        """
        rows = [
            {"row_id": "cluster-1-row-1", "equation_body": r"\dfrac{a + b}{c}"},
            {"row_id": "cluster-2-row-5", "equation_body": r"\frac{a+b}{c}"},
            {"row_id": "cluster-3-row-2", "equation_body": r"\tfrac{a + b}{c} \,"},
        ]
        sigs = {row["row_id"]: canonical_signature(row["equation_body"]) for row in rows}
        distinct_sigs = set(sigs.values())
        assert len(distinct_sigs) == 1, f"equivalent equations hashed to {sigs}"

    def test_distinct_equations_do_not_collide(self) -> None:
        """Equations that are NOT equivalent under ``normalize_eqn_body``
        (different RHS; single-letter case differences per commit-3 lexical
        guard) MUST hash to distinct signatures.
        """
        sig_a = canonical_signature(r"\frac{a}{b}")
        sig_b = canonical_signature(r"\frac{a}{c}")
        sig_c = canonical_signature(r"X^{IJ}")
        sig_d = canonical_signature(r"X^{JI}")  # multi-index symmetry NOT folded (commit 3 guard)
        assert len({sig_a, sig_b, sig_c, sig_d}) == 4

    def test_signature_is_hex_sha256_over_normalized_body(self) -> None:
        """The sha256 input is the commit-3-normalized equation body;
        neither kdoc ID nor equation number contributes to the digest.
        """
        from gpd.core.eqn_normalize import normalize_eqn_body

        body = r"E = m c^2"
        expected = hashlib.sha256(normalize_eqn_body(body).encode("utf-8")).hexdigest()
        assert canonical_signature(body) == expected
        # Length invariant.
        assert len(canonical_signature(body)) == 64
        assert re.fullmatch(r"[0-9a-f]{64}", canonical_signature(body))

    def test_normalize_fn_is_injectable(self) -> None:
        """Test fixtures MAY pass a pre-normalized corpus with an identity
        function for ``normalize_fn`` to isolate grouping from normalization.
        """
        sig_identity = canonical_signature("foo", normalize_fn=lambda s: s)
        assert sig_identity == hashlib.sha256(b"foo").hexdigest()

    def test_non_string_input_raises(self) -> None:
        with pytest.raises(TypeError):
            canonical_signature(42)  # type: ignore[arg-type]


# --- (2) topic-keyword grouping ---------------------------------------------


class TestTopicKeywordGrouping:
    """Brief 002 §Commit 6 Test 2."""

    def test_distinct_topics_separate_into_distinct_buckets(self) -> None:
        """Rows on separate topics land in separate keyword buckets; shared
        vocabulary does NOT leak a row across unrelated axes.
        """
        rows = [
            {"row_id": "r1", "description": "metric signature mostly-plus"},
            {"row_id": "r2", "description": "gauge group SU(N) with traceless Hermitian"},
            {"row_id": "r3", "description": "fermion representation 16-component Majorana"},
        ]
        vocab = ["metric", "gauge", "fermion"]
        buckets = topic_keyword_group(rows, vocab)

        assert set(buckets.keys()) == {"metric", "gauge", "fermion"}
        assert [r["row_id"] for r in buckets["metric"]] == ["r1"]
        assert [r["row_id"] for r in buckets["gauge"]] == ["r2"]
        assert [r["row_id"] for r in buckets["fermion"]] == ["r3"]

    def test_multi_topic_rows_surface_in_every_matched_bucket(self) -> None:
        """A row that mentions two vocab terms appears in BOTH buckets — the
        meta-auditor cross-references intersections in §2.
        """
        rows = [
            {"row_id": "r1", "description": "metric signature interacts with the gauge fixing"},
        ]
        buckets = topic_keyword_group(rows, ["metric", "gauge"])
        assert len(buckets["metric"]) == 1
        assert len(buckets["gauge"]) == 1
        assert buckets["metric"][0]["row_id"] == "r1"

    def test_unmatched_rows_absent_from_all_buckets(self) -> None:
        """Rows matching NO keyword are absent from the returned buckets; the
        meta-auditor surfaces them via ``append_to_candidate_axes``.
        """
        rows = [
            {"row_id": "r1", "description": "alpha-prime coupling bookkeeping"},
        ]
        buckets = topic_keyword_group(rows, ["metric", "gauge"])
        assert buckets == {"metric": [], "gauge": []}

    def test_vocab_is_lowercased_and_deduplicated(self) -> None:
        """Keyword match is case-insensitive; duplicate vocab entries (or
        casing variants) collapse to a single bucket.
        """
        rows = [
            {"row_id": "r1", "description": "METRIC signature axis"},
        ]
        buckets = topic_keyword_group(rows, ["Metric", "metric", "METRIC"])
        assert list(buckets.keys()) == ["metric"]
        assert len(buckets["metric"]) == 1

    def test_rejects_non_string_description_without_crashing(self) -> None:
        """A malformed upstream cluster row (non-string description) is
        treated as unmatched rather than crashing the grouping pass.
        """
        rows = [
            {"row_id": "r1", "description": None},
            {"row_id": "r2", "description": "metric signature"},
        ]
        buckets = topic_keyword_group(rows, ["metric"])
        assert [r["row_id"] for r in buckets["metric"]] == ["r2"]


# --- (3) residual-row queue writer ------------------------------------------


class TestResidualRowToCandidateAxes:
    """Brief 002 §Commit 6 Test 3."""

    def test_first_append_creates_file_with_header(self, tmp_path: Path) -> None:
        """First append creates the candidate-axes queue file with the
        canonical header AND the row appended as a markdown table line.
        """
        path = tmp_path / "GPD" / "meta-audit" / "candidate-axes.md"
        row = {
            "row_id": "cluster-1-row-17",
            "description": "BMN μ normalisation factor-of-3",
            "proposed_axis_id": None,
            "status": "pending",
            "reviewer_notes": "",
        }

        append_to_candidate_axes(row, path)

        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert content.startswith(CANDIDATE_AXES_HEADER)
        # Row appended verbatim on a single line.
        appended = content[len(CANDIDATE_AXES_HEADER) :]
        assert appended.strip().startswith("| cluster-1-row-17 |")
        assert "BMN μ normalisation factor-of-3" in appended
        assert appended.strip().endswith("|")

    def test_appends_preserve_queue_format_and_are_append_only(self, tmp_path: Path) -> None:
        """Multiple sequential appends stack under the shared header; no
        prior row is overwritten.
        """
        path = tmp_path / "candidate-axes.md"
        append_to_candidate_axes({"row_id": "r1", "description": "first"}, path)
        append_to_candidate_axes({"row_id": "r2", "description": "second"}, path)
        append_to_candidate_axes({"row_id": "r3", "description": "third"}, path)

        content = path.read_text(encoding="utf-8")
        # Header present exactly once (no duplication on re-append).
        assert content.count(CANDIDATE_AXES_HEADER) == 1
        # Every appended row is present, in insertion order.
        appended_body = content[len(CANDIDATE_AXES_HEADER) :]
        lines = [ln for ln in appended_body.strip().splitlines() if ln.startswith("|")]
        assert len(lines) == 3
        assert " r1 " in lines[0]
        assert " r2 " in lines[1]
        assert " r3 " in lines[2]

    def test_defaults_status_to_pending_and_fills_missing_fields(self, tmp_path: Path) -> None:
        """Rows that omit ``status`` default to ``pending`` per the
        controlled-vocab queue contract; missing optional fields render as
        empty cells so the markdown table stays aligned.
        """
        path = tmp_path / "queue.md"
        append_to_candidate_axes({"row_id": "r-minimal", "description": "d"}, path)
        line = path.read_text(encoding="utf-8").strip().splitlines()[-1]
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        # columns: row_id | description | proposed_axis_id | status | reviewer_notes
        assert cells == ["r-minimal", "d", "", "pending", ""]

    def test_escapes_pipes_and_strips_newlines(self, tmp_path: Path) -> None:
        """Pipes embedded in description cells are escaped; embedded newlines
        are stripped so the row stays on a single markdown line.
        """
        path = tmp_path / "queue.md"
        append_to_candidate_axes(
            {
                "row_id": "r-pipe",
                "description": "value\nwith|pipe",
                "reviewer_notes": "multi|line|note",
            },
            path,
        )
        content = path.read_text(encoding="utf-8")
        # The single appended row must be exactly one line of text.
        appended = content[len(CANDIDATE_AXES_HEADER) :].strip()
        assert "\n" not in appended
        assert r"\|" in appended  # pipe escaped
        assert "value with" in appended  # newline stripped to space


# --- (4) meta-audit schema validation vs BFSS fixture -----------------------


class TestMetaAuditSchemaMatchesBfssFixture:
    """Brief 002 §Commit 6 acceptance criterion: ``meta-audit-schema.md``
    MUST validate against the BFSS-bootstrap hand-built cross-cluster
    fixture §§1–8. The fixture lives in the sibling BFSS-bootstrap project
    at a conventional path; if it is absent (CI without the PSI projects
    tree), the test is skipped rather than erroring.

    This is the load-bearing anti-drift anchor for the schema — the
    meta-auditor emits reports against this schema, and the BFSS fixture is
    the ground-truth shape the schema must keep validating.
    """

    BFSS_FIXTURE = Path(
        "D:/Data/Dropbox/PSI/projects/bfss-bootstrap/agents/reports/cross-cluster-meta-audit.md"
    )

    # §§1–8 canonical section headings. Order is load-bearing per
    # `meta-audit-schema.md`; drift here indicates schema decoupling.
    EXPECTED_SECTIONS = [
        r"^##\s+1\.\s+Consistency Summary",
        r"^##\s+2\.\s+Inter-Cluster Contradictions Flagged",
        r"^##\s+3\.\s+Master Convention Reconciliation Table",
        r"^##\s+4\.\s+Aggregate Typo List",
        r"^##\s+5\.\s+Open Questions",
        r"^##\s+6\.\s+Cross-Cluster Consistency Audit Detail",
        r"^##\s+7\.\s+Compliance Checklist",
        r"^##\s+8\.\s+Journal Entry",
    ]

    def _schema_has_section(self, schema_text: str, section_pattern: str) -> bool:
        return re.search(section_pattern, schema_text, flags=re.MULTILINE) is not None

    def _fixture_has_section(self, fixture_text: str, section_pattern: str) -> bool:
        return re.search(section_pattern, fixture_text, flags=re.MULTILINE) is not None

    def test_schema_template_exists(self) -> None:
        """The schema template file MUST exist at the installed path."""
        assert _SCHEMA_PATH.exists(), f"missing schema template: {_SCHEMA_PATH}"

    def test_schema_has_every_section_from_1_to_8(self) -> None:
        """Every §1–§8 heading from the BFSS fixture is present in the
        installed schema template."""
        schema = _SCHEMA_PATH.read_text(encoding="utf-8")
        missing = [pat for pat in self.EXPECTED_SECTIONS if not self._schema_has_section(schema, pat)]
        assert not missing, f"schema missing section headings: {missing}"

    def test_schema_sections_appear_in_monotonic_order(self) -> None:
        """§1 through §8 occur in increasing order in the schema; a reorder
        would silently break meta-audit reports that render against the
        schema's ordering."""
        schema = _SCHEMA_PATH.read_text(encoding="utf-8")
        positions = []
        for pat in self.EXPECTED_SECTIONS:
            match = re.search(pat, schema, flags=re.MULTILINE)
            assert match is not None, f"section not found: {pat}"
            positions.append(match.start())
        assert positions == sorted(positions), (
            "schema §§1–8 headings out of order: " + repr(positions)
        )

    def test_bfss_fixture_satisfies_schema_sections(self) -> None:
        """Sanity-check the BFSS fixture carries the same §§1–8 sections the
        schema advertises — this is what makes the schema a faithful
        specification of the fixture. Skipped when the BFSS project tree is
        absent (e.g. CI runner without the PSI shared directory).
        """
        if not self.BFSS_FIXTURE.exists():
            pytest.skip(f"BFSS fixture unavailable at {self.BFSS_FIXTURE}")
        fixture = self.BFSS_FIXTURE.read_text(encoding="utf-8")
        missing = [pat for pat in self.EXPECTED_SECTIONS if not self._fixture_has_section(fixture, pat)]
        assert not missing, f"BFSS fixture missing sections schema asserts: {missing}"
