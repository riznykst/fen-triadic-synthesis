"""Tests for the ARK/w3id PID helpers (ADR-003)."""
from __future__ import annotations

import pytest

from services.common.pid import KIND_TO_PATH, mint_ark, n2t_uri, w3id_uri


def test_mint_ark_format():
    assert mint_ark("99999", "g", 42) == "ark:99999/g00042"


def test_mint_ark_pads_to_five_digits():
    assert mint_ark("99999", "r", 7) == "ark:99999/r00007"
    assert mint_ark("99999", "v", 123456) == "ark:99999/v123456"


def test_n2t_uri():
    assert n2t_uri("99999", "g", 42) == "https://n2t.net/ark:99999/g00042"


def test_w3id_uri_all_kinds():
    assert w3id_uri("g", 42) == "https://w3id.org/fen/id/decision/g00042"
    assert w3id_uri("v", 42) == "https://w3id.org/fen/id/validation/v00042"
    assert w3id_uri("r", 42) == "https://w3id.org/fen/id/reputation-snapshot/r00042"
    assert w3id_uri("s", 42) == "https://w3id.org/fen/id/session/s00042"


def test_w3id_uri_accepts_string_ref():
    assert w3id_uri("g", "00042") == "https://w3id.org/fen/id/decision/g00042"
    assert w3id_uri("g", "g00042") == "https://w3id.org/fen/id/decision/g00042"


def test_w3id_uri_unknown_kind_raises():
    with pytest.raises(ValueError):
        w3id_uri("x", 1)


def test_kind_to_path_is_complete():
    assert set(KIND_TO_PATH) == {"g", "v", "r", "s"}
