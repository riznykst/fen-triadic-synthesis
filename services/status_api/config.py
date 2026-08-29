"""Env-driven settings for the Status API."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class StatusApiConfig:
    sparql_query_endpoint: str
    sparql_ping_endpoint: str
    cors_origins: list
    web_dir: str

    @classmethod
    def from_env(cls) -> "StatusApiConfig":
        origins = os.getenv("FEN_CORS_ORIGINS", "*")
        return cls(
            sparql_query_endpoint=os.getenv("SPARQL_QUERY_ENDPOINT", "http://localhost:3030/fen/query"),
            # Explicit ping URL — deriving it by string surgery on the query
            # endpoint is brittle (custom paths, Virtuoso etc.).
            sparql_ping_endpoint=os.getenv("SPARQL_PING_ENDPOINT", "http://localhost:3030/$/ping"),
            cors_origins=[o.strip() for o in origins.split(",") if o.strip()],
            web_dir=os.getenv("FEN_WEB_DIR", "web"),
        )
