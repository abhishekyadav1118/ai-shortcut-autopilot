"""Unit tests for json_repair utility."""

import pytest

from autopilot.utils.json_repair import repair_and_parse_json


def test_repair_clean_json():
    raw = '{"key": "value", "list": [1, 2, 3]}'
    assert repair_and_parse_json(raw) == {"key": "value", "list": [1, 2, 3]}


def test_repair_markdown_fences():
    raw = '```json\n{"status": "ok"}\n```'
    assert repair_and_parse_json(raw) == {"status": "ok"}


def test_repair_unterminated_string():
    # Simulates cut-off LLM output mid-string
    raw = '{"claims": [{"text": "Claim 1", "status": "SUPPORTED"}], "unsupported_count": 0, "notes": "Some cut-off string'
    repaired = repair_and_parse_json(raw)
    assert repaired["claims"][0]["status"] == "SUPPORTED"
    assert repaired["unsupported_count"] == 0


def test_repair_unclosed_nested_structures():
    # Simulates cut-off inside array of objects
    raw = '{"claims": [{"text": "Claim 1", "status": "SUPPORTED"}, {"text": "Claim 2'
    repaired = repair_and_parse_json(raw)
    assert len(repaired["claims"]) >= 1


def test_repair_invalid_json_raises():
    with pytest.raises(ValueError, match="Invalid JSON"):
        repair_and_parse_json("{completely invalid ::: broken")
