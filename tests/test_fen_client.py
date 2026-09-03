"""Tests for FenClient — the one pipeline component whose contract is
"never raise, log and drop" (services/fen_bridge/fen_client.py). Its whole
failure mode must be verified: success forwards and returns True; transient
failures retry with backoff; terminal failure returns False; nothing raises
(TECH-DEBT P2 test blind spot).
"""
from __future__ import annotations

from unittest import mock

import requests

from services.fen_bridge.fen_client import FenClient


def test_submit_candidates_returns_true_on_success():
    resp = mock.Mock()
    resp.status_code = 200
    resp.raise_for_status.return_value = None
    client = FenClient("http://fen:8100/", timeout_s=1.0)

    with mock.patch.object(requests, "post", return_value=resp) as post:
        ok = client.submit_candidates([{"annotation_id": "a1"}])

    assert ok is True
    assert post.call_count == 1
    url = post.call_args.args[0]
    assert url == "http://fen:8100/candidates"  # trailing slash stripped
    assert post.call_args.kwargs["json"] == {"candidates": [{"annotation_id": "a1"}]}


def test_submit_candidates_retries_transient_failures_then_recovers():
    """A transient failure (connection error) must be retried — with
    backoff — and a later success returns True."""
    side_effects = [requests.ConnectionError("boom"), mock.Mock(status_code=200)]
    resp_ok = side_effects[1]
    resp_ok.raise_for_status.return_value = None
    client = FenClient("http://fen:8100", timeout_s=1.0, max_retries=2)

    with mock.patch.object(requests, "post", side_effect=side_effects) as post:
        with mock.patch("services.fen_bridge.fen_client.time.sleep") as sleep:
            ok = client.submit_candidates([{"annotation_id": "a1"}])

    assert ok is True
    assert post.call_count == 2
    sleep.assert_called_once_with(0.5)  # backoff after the first attempt


def test_submit_candidates_returns_false_after_terminal_failure():
    """Retries exhausted -> False, and it NEVER raises (the module's whole
    point: a candidate that fails to reach FEN stays gfen:pending and is
    redelivered later; the caller decides what to do)."""
    client = FenClient("http://fen:8100", timeout_s=1.0, max_retries=2)

    with mock.patch.object(
        requests, "post", side_effect=requests.HTTPError("500 Internal Server Error")
    ) as post:
        with mock.patch("services.fen_bridge.fen_client.time.sleep"):
            ok = client.submit_candidates([{"annotation_id": "a1"}])

    assert ok is False
    assert post.call_count == 3  # initial + max_retries(2)


def test_submit_candidates_handles_http_4xx_as_failure():
    """HTTP 422/4xx (rejected batch) is a RequestException via
    raise_for_status -> retried and finally False, never raised."""
    resp = mock.Mock()
    resp.raise_for_status.side_effect = requests.HTTPError("422 Unprocessable Entity")
    client = FenClient("http://fen:8100", timeout_s=1.0, max_retries=1)

    with mock.patch.object(requests, "post", return_value=resp) as post:
        with mock.patch("services.fen_bridge.fen_client.time.sleep"):
            ok = client.submit_candidates([{"annotation_id": "a1"}])

    assert ok is False
    assert post.call_count == 2
