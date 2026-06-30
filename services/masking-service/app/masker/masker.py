"""
PII pseudonymizer for Sentinel.

Converts plaintext identifiers to stable tokens before any data leaves
toward llm-orchestrator. Only this service holds the reverse-map.

Guarantee: for the same incident_id, the same plaintext always maps to
the same token — ensuring consistency within one LLM call.
"""

from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass, field


@dataclass
class ReverseMap:
    """Per-incident mapping from token → plaintext. TTL is managed by the caller."""

    incident_id: str
    token_to_plain: dict[str, str] = field(default_factory=dict)
    plain_to_token: dict[str, str] = field(default_factory=dict)


class Masker:
    """
    Thread-safe, incident-scoped pseudonymizer.

    Tokens are deterministic within an incident (sha256 of incident_id + plaintext)
    and opaque across incidents (no global counter that leaks ordering).
    """

    # Prefix per identifier type keeps tokens human-readable in the LLM prompt.
    _PREFIX = {
        "user": "user_",
        "host": "host_",
        "ip": "ip_",
        "email": "email_",
    }

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._maps: dict[str, ReverseMap] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def mask(self, incident_id: str, kind: str, plaintext: str) -> str:
        """Return a stable pseudonym token for plaintext within this incident."""
        if not plaintext:
            return plaintext

        with self._lock:
            rmap = self._maps.setdefault(incident_id, ReverseMap(incident_id=incident_id))
            key = f"{kind}:{plaintext}"
            if key in rmap.plain_to_token:
                return rmap.plain_to_token[key]

            token = self._make_token(kind, incident_id, plaintext)
            rmap.plain_to_token[key] = token
            rmap.token_to_plain[token] = plaintext
            return token

    def unmask(self, incident_id: str, token: str) -> str | None:
        """Reverse a token back to plaintext. Returns None if unknown."""
        with self._lock:
            rmap = self._maps.get(incident_id)
            if rmap is None:
                return None
            return rmap.token_to_plain.get(token)

    def get_reverse_map(self, incident_id: str) -> dict[str, str]:
        """Return a copy of the full token→plaintext map for an incident."""
        with self._lock:
            rmap = self._maps.get(incident_id)
            if rmap is None:
                return {}
            return dict(rmap.token_to_plain)

    def delete_map(self, incident_id: str) -> None:
        """Delete the reverse-map for an incident (called after case-service un-masks)."""
        with self._lock:
            self._maps.pop(incident_id, None)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @classmethod
    def _make_token(cls, kind: str, incident_id: str, plaintext: str) -> str:
        digest = hashlib.sha256(f"{incident_id}:{kind}:{plaintext}".encode()).hexdigest()
        prefix = cls._PREFIX.get(kind, "tok_")
        return f"{prefix}{digest[:6]}"
