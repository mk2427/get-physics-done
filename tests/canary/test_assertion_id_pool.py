from __future__ import annotations

import threading
from pathlib import Path

from assertion_id_pool import AssertionIdPool


def test_empty_assertion_dir_reserves_a001(tmp_path: Path) -> None:
    pool = AssertionIdPool(tmp_path)
    assert pool.reserve().reserved_id == "A-001"


def test_existing_assertions_reserve_next(tmp_path: Path) -> None:
    (tmp_path / "A-001-one.md").write_text("", encoding="utf-8")
    (tmp_path / "A-002-two.md").write_text("", encoding="utf-8")
    pool = AssertionIdPool(tmp_path)
    assert pool.reserve().reserved_id == "A-003"


def test_live_registry_empty_sandbox_reserves_from_registry(tmp_path: Path) -> None:
    registry = tmp_path / "registry"
    sandbox = tmp_path / "sandbox"
    registry.mkdir()
    sandbox.mkdir()
    (registry / "A-001-one.md").write_text("", encoding="utf-8")
    (registry / "A-002-two.md").write_text("", encoding="utf-8")
    pool = AssertionIdPool(registry)
    reservation = pool.reserve(output_assertion_dir=sandbox)
    assert reservation.reserved_id == "A-003"


def test_parallel_reservations_are_unique(tmp_path: Path) -> None:
    pool = AssertionIdPool(tmp_path)
    out: list[str] = []
    lock = threading.Lock()

    def worker() -> None:
        rid = pool.reserve().reserved_id
        with lock:
            out.append(rid)

    threads = [threading.Thread(target=worker) for _ in range(12)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(out) == [f"A-{i:03d}" for i in range(1, 13)]
