"""Validation Result Consumer — applies governance decisions into the RDF
named graph and publishes confirmations (ADR-001: content stays in Virtuoso,
only governance provenance is written)."""

__all__ = ["config", "main", "sparql_updater"]
