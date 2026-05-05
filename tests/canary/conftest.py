import sys
from pathlib import Path

import pytest

_CANARY_DIR = Path(__file__).resolve().parent
if str(_CANARY_DIR) not in sys.path:
    sys.path.insert(0, str(_CANARY_DIR))


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "canary: marks tests as requiring the local BFSS corpus (deselect with -m 'not canary')",
    )
