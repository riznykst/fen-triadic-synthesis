"""ARK / w3id.org PID helpers for FEN governance records (ADR-003).

Scheme (same pattern as GRAPHIA D2.2 section 4.5, own NAAN for FEN):

    ark:{NAAN}/{kind}{seq:05d}
        g -> governance decision     https://w3id.org/fen/id/decision/gNNNNN
        v -> validation record       https://w3id.org/fen/id/validation/vNNNNN
        r -> reputation snapshot     https://w3id.org/fen/id/reputation-snapshot/rNNNNN
        s -> scaffolding session     https://w3id.org/fen/id/session/sNNNNN

Resolution: https://n2t.net/ark:{NAAN}/...  --303-->  https://w3id.org/fen/id/...

A PID is stable and independent of any blockchain explorer; the on-chain tx
hash is only the ``gfen:ledgerAnchor`` attribute of a record, never its
identifier.
"""
from __future__ import annotations

import os
from typing import Union

KIND_TO_PATH = {
    "g": "decision",
    "v": "validation",
    "r": "reputation-snapshot",
    "s": "session",
}

W3ID_BASE = "https://w3id.org/fen"
N2T_BASE = "https://n2t.net"

DEFAULT_NAAN = "99999"


def default_naan() -> str:
    """NAAN from the environment (FEN_NAAN), falling back to the local-dev value."""
    return os.getenv("FEN_NAAN", DEFAULT_NAAN)


def _assigned_name(kind: str, seq: Union[int, str]) -> str:
    if kind not in KIND_TO_PATH:
        raise ValueError(f"unknown PID kind {kind!r}; expected one of {sorted(KIND_TO_PATH)}")
    return f"{kind}{int(seq):05d}"


def mint_ark(naan: str, kind: str, seq: Union[int, str]) -> str:
    """Return the ARK string, e.g. ``ark:99999/g00042``."""
    return f"ark:{naan}/{_assigned_name(kind, seq)}"


def n2t_uri(naan: str, kind: str, seq: Union[int, str]) -> str:
    """Return the N2T resolution URL for an ARK, e.g. https://n2t.net/ark:99999/g00042."""
    return f"{N2T_BASE}/ark:{naan}/{_assigned_name(kind, seq)}"


def w3id_uri(kind: str, ref: Union[int, str]) -> str:
    """Return the dereferenceable w3id URI, e.g. https://w3id.org/fen/id/decision/g00042."""
    assigned = _assigned_name(kind, ref)  # validates `kind` first
    return f"{W3ID_BASE}/id/{KIND_TO_PATH[kind]}/{assigned}"
