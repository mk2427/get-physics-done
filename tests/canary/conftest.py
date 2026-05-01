import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "canary: marks tests as requiring the local BFSS corpus (deselect with -m 'not canary')",
    )
