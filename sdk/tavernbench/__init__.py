"""TavernBench Behavior Lab HTTP v1 SDK."""
from .client import (
    CANONICALIZATION,
    PROTOCOL_VERSION,
    SUPPORTED_ACTIONS,
    Client,
    ConfigurationError,
    ProtocolError,
    Run,
    TavernBenchError,
    TransportError,
    TypedError,
    canonical_trace_sha256,
    verify_evidence,
)

__version__ = "0.2.0"

__all__ = [
    "CANONICALIZATION",
    "PROTOCOL_VERSION",
    "SUPPORTED_ACTIONS",
    "Client",
    "ConfigurationError",
    "ProtocolError",
    "Run",
    "TavernBenchError",
    "TransportError",
    "TypedError",
    "canonical_trace_sha256",
    "verify_evidence",
]
