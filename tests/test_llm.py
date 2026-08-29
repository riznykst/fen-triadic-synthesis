"""Tests for the pluggable OpenAI-compatible LLM provider."""
from __future__ import annotations

from unittest import mock

from services.common.llm import LLMConfig, chat_completion, parse_outcome


def _config(base="https://api.example.com/v1", key="k", model="m") -> LLMConfig:
    cfg = LLMConfig()
    cfg.base_url = base
    cfg.api_key = key
    cfg.model = model
    cfg.timeout_s = 5.0
    return cfg


def test_chat_completion_success():
    cfg = _config()
    with mock.patch("services.common.llm.requests.post") as post:
        post.return_value.status_code = 200
        post.return_value.json.return_value = {"choices": [{"message": {"content": "validated"}}]}
        assert chat_completion(cfg, "sys", "usr") == "validated"
    _, kwargs = post.call_args
    assert kwargs["json"]["model"] == "m"
    assert kwargs["headers"]["Authorization"] == "Bearer k"
    assert kwargs["json"]["messages"][0]["role"] == "system"


def test_chat_completion_disabled_when_no_base_url():
    cfg = _config(base=None)
    assert chat_completion(cfg, "s", "u") is None


def test_chat_completion_network_error_returns_none():
    cfg = _config()
    with mock.patch("services.common.llm.requests.post", side_effect=Exception("boom")):
        assert chat_completion(cfg, "s", "u") is None


def test_chat_completion_malformed_response_returns_none():
    cfg = _config()
    with mock.patch("services.common.llm.requests.post") as post:
        post.return_value.status_code = 200
        post.return_value.json.side_effect = ValueError("bad json")
        assert chat_completion(cfg, "s", "u") is None


def test_parse_outcome_matches_allowed_anywhere_in_text():
    assert parse_outcome("VALIDATED", ("validated", "disputed", "rejected")) == "validated"
    assert parse_outcome("I would say disputed, because...", ("validated", "disputed", "rejected")) == "disputed"
    assert parse_outcome("rejected on quality grounds", ("validated", "disputed", "rejected")) == "rejected"


def test_parse_outcome_returns_none_when_no_match_or_empty():
    assert parse_outcome("maybe", ("validated", "disputed", "rejected")) is None
    assert parse_outcome(None, ("validated", "disputed", "rejected")) is None
    assert parse_outcome("", ("validated", "disputed", "rejected")) is None
