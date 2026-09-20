"""Pytest fixtures and test environment setup."""

import json
from pathlib import Path

import pytest

from autopilot.models import Script


@pytest.fixture
def sample_script_path() -> Path:
    return Path(__file__).parent / "fixtures" / "sample_script.json"


@pytest.fixture
def sample_script_data(sample_script_path: Path) -> dict:
    with open(sample_script_path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sample_script(sample_script_data: dict) -> Script:
    return Script(**sample_script_data)
