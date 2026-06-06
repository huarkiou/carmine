"""Test fixtures for pipeline/specs tests."""
import json
from pathlib import Path
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def config_3170():
    """Pre-captured getParamConf response for series 3170 (Audi A3)."""
    with open(FIXTURES / "config_3170.json", "r", encoding="utf-8") as f:
        return json.load(f)
