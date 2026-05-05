from __future__ import annotations

from pathlib import Path

from gpd.core.sympy_oracle import extract_equations_from_kdoc


def test_bold_parenthesized_display_equations_extract(tmp_path: Path) -> None:
    kdoc = tmp_path / "K-002-snippet.md"
    kdoc.write_text(
        "**(K.1)** One-matrix Hamiltonian:\n"
        "$$H = P^2 + X^4$$\n\n"
        "**(K.2)** Moment matrix:\n"
        "$$M_{ij} = <O_i O_j>$$\n",
        encoding="utf-8",
    )
    assert extract_equations_from_kdoc(kdoc) == [
        ("K.1", "H = P^2 + X^4"),
        ("K.2", "M_{ij} = <O_i O_j>"),
    ]


def test_live_k002_extracts_at_least_ten_equations() -> None:
    root = Path(__file__).resolve().parents[2]
    kdoc = root / "GPD" / "knowledge" / "K-002-adams-thermal-conic-bootstrap.md"
    equations = extract_equations_from_kdoc(kdoc)
    assert len(equations) >= 10
