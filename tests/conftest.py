"""Test fixtures: ensure each test gets a fresh Machine singleton."""

from __future__ import annotations

import pytest

from deuspy.machine import reset_machine


@pytest.fixture(autouse=True)
def _fresh_machine():
    reset_machine()
    yield
    reset_machine()
