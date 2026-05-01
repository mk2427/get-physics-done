"""Build the BFSS typo+axis truth-table fixture (plan-006 §C7).

Reads the two Stable BFSS knowledge files and emits
``tests/canary/fixtures/bfss-typo-axis-truth.json`` with the schema::

    {
      "axes": [
        {"id": int, "name": str, "regime": str, "BLOCKING": bool},
        ...  # 16 entries
      ],
      "typos_confirmed":   [...10 entries...],
      "typos_inconclusive": [...2 entries...],
      "typos_not_typo":    [...remaining entries...]
    }

Per plan-006 §C7 (post-iter-1-W2 fix): §3 of part-c carries THREE
classifications (CONFIRMED / INCONCLUSIVE / NOT-TYPO). The C7 PASS
gate uses ``typos_confirmed`` ONLY; the other two lists are reported
separately (informational + over-claim guard).

Source files (verified to exist 2026-04-26):

- ``D:/Data/Dropbox/PSI/projects/bfss-bootstrap/knowledge/013-part-a-convention-lock.md``
  §1 summary table (rows 1–16) → ``axes``.
- ``D:/Data/Dropbox/PSI/projects/bfss-bootstrap/knowledge/013-part-c-typos-questions-traps.md``
  §3 mapping table (top of §3) → ``typos_confirmed`` / ``typos_inconclusive``;
  §3 NOT-TYPO notes (T-007/T-008/T-011/T-012/T-017..T-025) → ``typos_not_typo``.

Resolves iter-3-W2: ``--source-dir`` overrides the default absolute
path so the builder works in CI / sandboxes / contributor checkouts
without the live BFSS knowledge tree.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_SOURCE_DIR = Path(
    "D:/Data/Dropbox/PSI/projects/bfss-bootstrap/knowledge"
)
DEFAULT_OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "bfss-typo-axis-truth.json"
)

# Axis 7 (γ^{10} Euclidean hermiticity) is the BLOCKING flag (Part A
# row #7; mirrored by Part C §5 O3 BLOCKING=YES).
_BLOCKING_AXIS_ID = 7


# ---------------------------------------------------------------------------
# Part A axis-table parser
# ---------------------------------------------------------------------------


_AXIS_ROW_RE = re.compile(
    r"^\|\s*(?P<id>\d+)\s*\|\s*(?P<name>[^|]+?)\s*\|\s*"
    r"(?P<choice>[^|]+?)\s*\|\s*(?P<source>[^|]+?)\s*\|\s*$"
)


def parse_axes(part_a_text: str) -> list[dict]:
    """Return the 16 axes as a list of dicts.

    Reads the §1 "Summary table of axes" then re-reads each per-axis
    section for the explicit ``Regime`` line. The BLOCKING flag is
    set ONLY on Axis 7 per Part A row #7.
    """
    rows: list[dict] = []
    in_summary_table = False
    for line in part_a_text.splitlines():
        # Detect the start of the summary table by its header row.
        if line.strip().startswith("| # | Axis |"):
            in_summary_table = True
            continue
        if not in_summary_table:
            continue
        # Skip the markdown separator row.
        if re.match(r"^\|[-\s|]+\|$", line.strip()):
            continue
        if not line.strip().startswith("|"):
            # Table ended.
            break
        m = _AXIS_ROW_RE.match(line)
        if m is None:
            continue
        axis_id = int(m.group("id"))
        name = m.group("name").strip()
        rows.append(
            {
                "id": axis_id,
                "name": name,
                "choice": m.group("choice").strip(),
                "source": m.group("source").strip(),
            }
        )
        if axis_id == 16:
            break

    if len(rows) != 16:
        raise ValueError(
            f"Expected 16 axes in Part A summary table; found {len(rows)}."
        )

    # Re-read per-axis sections for the Regime field.
    axis_id_to_regime: dict[int, str] = {}
    current_axis: int | None = None
    capture_next_regime = False
    for line in part_a_text.splitlines():
        m = re.match(r"^### Axis (\d+):", line)
        if m:
            current_axis = int(m.group(1))
            capture_next_regime = True
            continue
        if (
            capture_next_regime
            and current_axis is not None
            and line.lstrip().startswith("- **Regime**")
        ):
            # Strip the "- **Regime**:" prefix.
            regime = line.split(":", 1)[1].strip() if ":" in line else line
            # Drop trailing markdown punctuation.
            axis_id_to_regime[current_axis] = regime
            capture_next_regime = False

    out: list[dict] = []
    for r in rows:
        out.append(
            {
                "id": r["id"],
                "name": r["name"],
                "regime": axis_id_to_regime.get(r["id"], ""),
                "BLOCKING": r["id"] == _BLOCKING_AXIS_ID,
            }
        )
    return out


# ---------------------------------------------------------------------------
# Part C typo-mapping parser
# ---------------------------------------------------------------------------


_TYPO_MAPPING_ROW_RE = re.compile(
    r"^\|\s*(?P<prior>[^|]+?)\s*\|\s*\*\*(?P<canonical>T-\d+)\*\*\s*\|\s*"
    r"(?P<desc>[^|]+?)\s*\|\s*(?P<status>[^|]+?)\s*\|\s*$"
)


def parse_typo_mapping(part_c_text: str) -> tuple[list[dict], list[dict]]:
    """Return (typos_confirmed, typos_inconclusive) from §3 mapping table.

    Status strings in the mapping table are either "CONFIRMED ..." or
    "INCONCLUSIVE ...". Anything else raises.
    """
    confirmed: list[dict] = []
    inconclusive: list[dict] = []
    in_table = False
    for line in part_c_text.splitlines():
        if line.strip().startswith("| Prior Part-C draft (compact)"):
            in_table = True
            continue
        if not in_table:
            continue
        if re.match(r"^\|[-\s|]+\|$", line.strip()):
            continue
        if not line.strip().startswith("|"):
            break
        m = _TYPO_MAPPING_ROW_RE.match(line)
        if m is None:
            continue
        canonical = m.group("canonical")
        desc = m.group("desc").strip()
        status_raw = m.group("status").strip()
        entry = {"T_id": canonical, "description": desc, "status_raw": status_raw}
        if status_raw.upper().startswith("CONFIRMED"):
            entry["status"] = "CONFIRMED"
            confirmed.append(entry)
        elif status_raw.upper().startswith("INCONCLUSIVE"):
            entry["status"] = "INCONCLUSIVE"
            inconclusive.append(entry)
        else:
            raise ValueError(
                f"Unrecognised status in §3 mapping table for {canonical}: {status_raw!r}"
            )
    return confirmed, inconclusive


# ---------------------------------------------------------------------------
# NOT-TYPO parser — reads the per-line bullet block at the foot of §3
# ---------------------------------------------------------------------------

_NOT_TYPO_BULLET_RE = re.compile(
    r"^-\s+\*\*(?P<tid>T-\d+)\*\*\s*\((?P<short>[^)]+)\)"
)


def parse_not_typo(part_c_text: str) -> list[dict]:
    """Return the rejected NOT-TYPO entries from §3.

    Looks at the "Notes on NOT-TYPO adjudications" subsection bullets
    of the form ``- **T-NNN** (short description) — explanation``.
    """
    out: list[dict] = []
    in_section = False
    for line in part_c_text.splitlines():
        if line.startswith("### Notes on NOT-TYPO adjudications"):
            in_section = True
            continue
        if in_section and line.startswith("##"):
            # Next major section starts; stop.
            break
        if not in_section:
            continue
        m = _NOT_TYPO_BULLET_RE.match(line)
        if m is None:
            continue
        out.append(
            {
                "T_id": m.group("tid"),
                "description": m.group("short").strip(),
                "status": "NOT-TYPO",
            }
        )
    return out


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def build_truth_table(source_dir: Path) -> dict:
    part_a = source_dir / "013-part-a-convention-lock.md"
    part_c = source_dir / "013-part-c-typos-questions-traps.md"
    if not part_a.is_file():
        raise FileNotFoundError(f"Missing Part A at {part_a}")
    if not part_c.is_file():
        raise FileNotFoundError(f"Missing Part C at {part_c}")
    part_a_text = part_a.read_text(encoding="utf-8")
    part_c_text = part_c.read_text(encoding="utf-8")
    axes = parse_axes(part_a_text)
    confirmed, inconclusive = parse_typo_mapping(part_c_text)
    not_typo = parse_not_typo(part_c_text)
    return {
        "axes": axes,
        "typos_confirmed": confirmed,
        "typos_inconclusive": inconclusive,
        "typos_not_typo": not_typo,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build BFSS typo+axis truth-table fixture (plan-006 §C7)."
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=DEFAULT_SOURCE_DIR,
        help=(
            "Directory containing 013-part-a-convention-lock.md + "
            "013-part-c-typos-questions-traps.md (default: live BFSS path)."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Output JSON path (default: tests/canary/fixtures/bfss-typo-axis-truth.json).",
    )
    args = parser.parse_args(argv)

    table = build_truth_table(args.source_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(table, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wrote {args.output} with "
        f"{len(table['axes'])} axes, "
        f"{len(table['typos_confirmed'])} CONFIRMED, "
        f"{len(table['typos_inconclusive'])} INCONCLUSIVE, "
        f"{len(table['typos_not_typo'])} NOT-TYPO."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
