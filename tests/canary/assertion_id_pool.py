"""Thread-safe A-NNN reservation for canary assertion dispatch."""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

_ASSERTION_ID_RE = re.compile(r"^A-(\d{3})(?:-|\.|$)")


@dataclass(frozen=True)
class AssertionReservation:
    """One orchestrator-owned assertion ID reservation."""

    reserved_id: str
    dispatch_id: str | None = None
    output_assertion_dir: Path | None = None
    final_path: Path | None = None


class AssertionIdPool:
    """Reserve project-global top-level A-NNN IDs under a process lock."""

    def __init__(
        self,
        registry_assertion_dir: Path,
        *,
        starting_reservations: Iterable[str] = (),
    ) -> None:
        self.registry_assertion_dir = Path(registry_assertion_dir)
        self._lock = threading.Lock()
        self._reserved: set[int] = set()
        existing = self._scan_existing_ids(self.registry_assertion_dir)
        seeded = self._ids_from_strings(starting_reservations)
        self._next = max(existing | seeded, default=0) + 1
        self._reserved.update(seeded)

    @staticmethod
    def _ids_from_strings(values: Iterable[str]) -> set[int]:
        ids: set[int] = set()
        for value in values:
            match = _ASSERTION_ID_RE.match(str(value))
            if match:
                ids.add(int(match.group(1)))
        return ids

    @classmethod
    def _scan_existing_ids(cls, root: Path) -> set[int]:
        if not root.is_dir():
            return set()
        return cls._ids_from_strings(path.name for path in root.glob("A-*.md"))

    def reserve(
        self,
        *,
        dispatch_id: str | None = None,
        output_assertion_dir: Path | None = None,
    ) -> AssertionReservation:
        with self._lock:
            while self._next in self._reserved:
                self._next += 1
            numeric = self._next
            self._reserved.add(numeric)
            self._next += 1
        return AssertionReservation(
            reserved_id=f"A-{numeric:03d}",
            dispatch_id=dispatch_id,
            output_assertion_dir=output_assertion_dir,
        )


__all__ = ["AssertionIdPool", "AssertionReservation"]
