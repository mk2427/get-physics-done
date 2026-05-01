"""Manifest-integrity tests for the BFSS 16-paper canary corpus.

Marked ``@pytest.mark.canary`` — NOT part of the default CI suite.
Run only when the local BFSS corpus is available at the path recorded in
``bfss-corpus-manifest.json``.

Deselect with::

    pytest -m "not canary"

Run explicitly with::

    pytest tests/canary/test_bfss_corpus_manifest.py -v
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

_CANARY_DIR = Path(__file__).resolve().parent
_MANIFEST_PATH = _CANARY_DIR / "bfss-corpus-manifest.json"


def _load_manifest() -> dict:
    with _MANIFEST_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


@pytest.mark.canary
def test_all_16_pdfs_present() -> None:
    """Every entry in the manifest must point to an existing PDF file."""
    manifest = _load_manifest()
    entries = manifest["entries"]
    refs_dir = Path(manifest["references_dir"])

    missing: list[str] = []
    for entry in entries:
        pdf_path = refs_dir / entry["pdf_filename"]
        if not pdf_path.exists():
            missing.append(str(pdf_path))

    assert len(missing) == 0, f"{len(missing)} PDF(s) missing:\n" + "\n".join(missing)
    assert len(entries) == 16, f"Expected 16 entries, got {len(entries)}"


@pytest.mark.canary
def test_sha256_matches() -> None:
    """Every PDF's current SHA-256 must match the pinned value in the manifest."""
    manifest = _load_manifest()
    entries = manifest["entries"]
    refs_dir = Path(manifest["references_dir"])

    mismatches: list[str] = []
    for entry in entries:
        pdf_path = refs_dir / entry["pdf_filename"]
        if not pdf_path.exists():
            mismatches.append(f"MISSING: {pdf_path}")
            continue
        actual = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        expected = entry["sha256"]
        if actual != expected:
            mismatches.append(
                f"{entry['pdf_filename']}: got {actual}, expected {expected}"
            )

    assert len(mismatches) == 0, (
        f"{len(mismatches)} SHA-256 mismatch(es):\n" + "\n".join(mismatches)
    )


@pytest.mark.canary
def test_every_entry_has_tex_fields() -> None:
    """Every entry must have populated ``tex_filename``, ``tex_sha256``, ``source_format``."""
    manifest = _load_manifest()
    entries = manifest["entries"]

    missing: list[str] = []
    for entry in entries:
        for field in ("tex_filename", "tex_sha256", "source_format"):
            value = entry.get(field)
            if not isinstance(value, str) or not value:
                missing.append(f"{entry.get('arxiv_id', '<unknown>')}: {field}={value!r}")

    assert len(missing) == 0, (
        f"{len(missing)} missing/empty .tex field(s):\n" + "\n".join(missing)
    )


@pytest.mark.canary
def test_tex_filename_resolves_under_references_dir() -> None:
    """For each entry, ``references_dir / tex_filename`` must exist on disk."""
    manifest = _load_manifest()
    entries = manifest["entries"]
    refs_dir = Path(manifest["references_dir"])

    missing: list[str] = []
    for entry in entries:
        tex_rel = entry.get("tex_filename")
        if not isinstance(tex_rel, str) or not tex_rel:
            missing.append(f"{entry.get('arxiv_id', '<unknown>')}: no tex_filename")
            continue
        tex_path = refs_dir / tex_rel
        if not tex_path.exists():
            missing.append(str(tex_path))

    assert len(missing) == 0, (
        f"{len(missing)} .tex file(s) missing:\n" + "\n".join(missing)
    )
