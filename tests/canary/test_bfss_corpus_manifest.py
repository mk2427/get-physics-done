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
import os
from pathlib import Path

import pytest

_CANARY_DIR = Path(__file__).resolve().parent
_MANIFEST_PATH = _CANARY_DIR / "bfss-corpus-manifest.json"
_REFERENCES_DIR_ENV = "GPD_BFSS_REFERENCES_DIR"


def _load_manifest() -> dict:
    with _MANIFEST_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _sha256(path: Path, *, canonical_text: bool = False) -> str:
    data = path.read_bytes()
    if canonical_text:
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def _resolve_references_dir(manifest: dict) -> Path:
    override = os.environ.get(_REFERENCES_DIR_ENV)
    if override:
        refs_dir = Path(override).expanduser()
        if not refs_dir.exists():
            pytest.fail(f"{_REFERENCES_DIR_ENV} does not exist: {refs_dir}")
        return refs_dir

    refs_dir = Path(manifest["references_dir"])
    if refs_dir.exists():
        return refs_dir

    pytest.skip(
        "BFSS corpus unavailable; set "
        f"{_REFERENCES_DIR_ENV} to a local references directory or update "
        "bfss-corpus-manifest.json references_dir"
    )


def _missing_files(manifest: dict, filename_field: str, refs_dir: Path) -> list[str]:
    missing: list[str] = []
    for entry in manifest["entries"]:
        rel = entry.get(filename_field)
        if not isinstance(rel, str) or not rel:
            missing.append(f"{entry.get('arxiv_id', '<unknown>')}: no {filename_field}")
            continue
        path = refs_dir / rel
        if not path.exists():
            missing.append(str(path))
    return missing


def _hash_mismatches(
    manifest: dict,
    filename_field: str,
    hash_field: str,
    refs_dir: Path,
) -> list[str]:
    mismatches: list[str] = []
    for entry in manifest["entries"]:
        rel = entry.get(filename_field)
        if not isinstance(rel, str) or not rel:
            mismatches.append(f"{entry.get('arxiv_id', '<unknown>')}: no {filename_field}")
            continue
        path = refs_dir / rel
        if not path.exists():
            mismatches.append(f"MISSING: {path}")
            continue
        actual = _sha256(path, canonical_text=hash_field == "tex_sha256")
        expected = entry[hash_field]
        if actual != expected:
            mismatches.append(f"{rel}: got {actual}, expected {expected}")
    return mismatches


def test_configured_corpus_helper_accepts_matching_pdf_and_tex_hashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = tmp_path / "paper.pdf"
    tex_path = tmp_path / "sources" / "paper.tex"
    pdf_path.write_bytes(b"%PDF test corpus\n")
    tex_path.parent.mkdir()
    tex_path.write_bytes(b"\\begin{equation} X=Y \\end{equation}\r\n")
    monkeypatch.setenv(_REFERENCES_DIR_ENV, str(tmp_path))

    manifest = {
        "references_dir": "Z:/missing/bfss",
        "entries": [
            {
                "arxiv_id": "0000.00000",
                "pdf_filename": "paper.pdf",
                "sha256": _sha256(pdf_path),
                "tex_filename": "sources/paper.tex",
                "tex_sha256": _sha256(tex_path, canonical_text=True),
                "source_format": "tex",
            }
        ],
    }

    refs_dir = _resolve_references_dir(manifest)

    assert _missing_files(manifest, "pdf_filename", refs_dir) == []
    assert _missing_files(manifest, "tex_filename", refs_dir) == []
    assert _hash_mismatches(manifest, "pdf_filename", "sha256", refs_dir) == []
    assert _hash_mismatches(manifest, "tex_filename", "tex_sha256", refs_dir) == []


def test_configured_corpus_helper_flags_tex_hash_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tex_path = tmp_path / "sources" / "paper.tex"
    tex_path.parent.mkdir()
    tex_path.write_text("changed source", encoding="utf-8")
    monkeypatch.setenv(_REFERENCES_DIR_ENV, str(tmp_path))

    manifest = {
        "references_dir": "Z:/missing/bfss",
        "entries": [
            {
                "arxiv_id": "0000.00000",
                "tex_filename": "sources/paper.tex",
                "tex_sha256": "0" * 64,
            }
        ],
    }

    refs_dir = _resolve_references_dir(manifest)

    mismatches = _hash_mismatches(manifest, "tex_filename", "tex_sha256", refs_dir)
    assert len(mismatches) == 1
    assert mismatches[0].startswith("sources/paper.tex: got ")


def test_configured_corpus_helper_treats_tex_line_endings_as_canonical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tex_path = tmp_path / "sources" / "paper.tex"
    tex_path.parent.mkdir()
    tex_path.write_bytes(b"line one\r\nline two\r\n")
    monkeypatch.setenv(_REFERENCES_DIR_ENV, str(tmp_path))

    expected = hashlib.sha256(b"line one\nline two\n").hexdigest()
    manifest = {
        "references_dir": "Z:/missing/bfss",
        "entries": [
            {
                "arxiv_id": "0000.00000",
                "tex_filename": "sources/paper.tex",
                "tex_sha256": expected,
                "source_format": "tex",
            }
        ],
    }

    refs_dir = _resolve_references_dir(manifest)

    assert _hash_mismatches(manifest, "tex_filename", "tex_sha256", refs_dir) == []


@pytest.mark.canary
def test_all_16_pdfs_present() -> None:
    """Every entry in the manifest must point to an existing PDF file."""
    manifest = _load_manifest()
    entries = manifest["entries"]
    refs_dir = _resolve_references_dir(manifest)
    missing = _missing_files(manifest, "pdf_filename", refs_dir)

    assert len(missing) == 0, f"{len(missing)} PDF(s) missing:\n" + "\n".join(missing)
    assert len(entries) == 16, f"Expected 16 entries, got {len(entries)}"


@pytest.mark.canary
def test_sha256_matches() -> None:
    """Every PDF's current SHA-256 must match the pinned value in the manifest."""
    manifest = _load_manifest()
    refs_dir = _resolve_references_dir(manifest)
    mismatches = _hash_mismatches(manifest, "pdf_filename", "sha256", refs_dir)

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
    refs_dir = _resolve_references_dir(manifest)
    missing = _missing_files(manifest, "tex_filename", refs_dir)

    assert len(missing) == 0, (
        f"{len(missing)} .tex file(s) missing:\n" + "\n".join(missing)
    )


@pytest.mark.canary
def test_tex_sha256_matches() -> None:
    """Every TeX source file's SHA-256 must match the pinned manifest value."""
    manifest = _load_manifest()
    refs_dir = _resolve_references_dir(manifest)
    mismatches = _hash_mismatches(manifest, "tex_filename", "tex_sha256", refs_dir)

    assert len(mismatches) == 0, (
        f"{len(mismatches)} TeX SHA-256 mismatch(es):\n" + "\n".join(mismatches)
    )
