"""HTTP client that forwards candidate batches to the external FEN API.

Deliberately swallows delivery errors (log and continue) — this is the one
point in the pipeline where a failure must NOT block or stall anything; a
candidate that never reaches FEN simply stays ``gfen:pending`` (no blocking
points, D2.2 section 4.1). Contrast with ``sparql_updater.apply_update``,
which raises loudly for the opposite reason.
"""
from __future__ import annotations

import logging
import time
from typing import List

import requests

logger = logging.getLogger(__name__)


class FenClient:
    def __init__(self, base_url: str, timeout_s: float = 10.0, max_retries: int = 2):
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._max_retries = max_retries

    def submit_candidates(self, candidates: List[dict]) -> bool:
        """POST a batch to ``/candidates``. Returns True if accepted, False
        otherwise. Never raises — failures are logged and dropped.
        """
        url = f"{self._base_url}/candidates"
        for attempt in range(self._max_retries + 1):
            try:
                resp = requests.post(url, json={"candidates": candidates}, timeout=self._timeout_s)
                resp.raise_for_status()
                logger.info("forwarded %d candidate(s) to %s", len(candidates), url)
                return True
            except requests.RequestException:
                logger.exception("failed to forward %d candidate(s) to %s (attempt %d)",
                                 len(candidates), url, attempt + 1)
                if attempt < self._max_retries:
                    time.sleep(0.5 * (attempt + 1))
        return False
