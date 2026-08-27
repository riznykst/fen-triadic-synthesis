"""FEN Bridge — the only DAP-side component that talks to the external FEN
system (ADR-002): outbound consumer + inbound webhook, two independent
processes/images."""

__all__ = ["config", "fen_client", "kafka_io", "outbound", "webhook"]
