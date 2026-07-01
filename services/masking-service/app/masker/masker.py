"""
PII pseudonymizer for Sentinel.

Converts plaintext identifiers to stable tokens before any data leaves
toward llm-orchestrator. Only this service holds the reverse-map.

Two implementations:
- Masker: in-memory, single-replica. Used by unit tests and local dev.
- ElasticsearchMasker: ES-backed, multi-replica safe. Used in production (ADR-015).

Guarantee: for the same incident_id, the same plaintext always maps to the same token
because tokens are derived via sha256(incident_id:kind:plaintext) — deterministic
across replicas, so concurrent upserts converge to the same value.
"""

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from elasticsearch import AsyncElasticsearch


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


# ---------------------------------------------------------------------------
# ES-backed implementation (production)
# ---------------------------------------------------------------------------

_INDEX = "sentinel-masking-maps"

# Painless script: idempotent upsert of a single token mapping.
# Safe to retry under concurrent updates — converges to the same value.
_UPSERT_SCRIPT = (
    "if (ctx._source.plain_to_token == null) {"
    "  ctx._source.plain_to_token = [:];"
    "  ctx._source.token_to_plain = [:];"
    "}"
    "if (!ctx._source.plain_to_token.containsKey(params.key)) {"
    "  ctx._source.plain_to_token[params.key] = params.token;"
    "  ctx._source.token_to_plain[params.token] = params.plaintext;"
    "}"
)

_INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "incident_id": {"type": "keyword"},
            # Stored but not indexed — we only need exact retrieval, not search.
            "plain_to_token": {"type": "object", "enabled": False},
            "token_to_plain": {"type": "object", "enabled": False},
            "created_at": {"type": "date", "format": "epoch_millis"},
        }
    }
}


class ElasticsearchMasker:
    """
    ES-backed masker for production. Multi-replica safe.

    Token generation is deterministic (sha256), so concurrent replicas
    computing the same token converge without coordination.
    Upserts use a Painless script with retry_on_conflict=5 for safety.
    """

    _PREFIX = Masker._PREFIX  # reuse the same prefix table

    def __init__(self, es: AsyncElasticsearch) -> None:
        self._es = es

    async def ensure_index(self) -> None:
        """Create the masking-maps index if it doesn't exist. Call once at startup."""
        exists = await self._es.indices.exists(index=_INDEX)
        if not exists:
            await self._es.indices.create(index=_INDEX, body=_INDEX_MAPPING)

    @classmethod
    def _make_token(cls, kind: str, incident_id: str, plaintext: str) -> str:
        digest = hashlib.sha256(f"{incident_id}:{kind}:{plaintext}".encode()).hexdigest()
        prefix = cls._PREFIX.get(kind, "tok_")
        return f"{prefix}{digest[:6]}"

    async def mask(self, incident_id: str, kind: str, plaintext: str) -> str:
        if not plaintext:
            return plaintext
        key = f"{kind}:{plaintext}"
        token = self._make_token(kind, incident_id, plaintext)
        await self._es.update(
            index=_INDEX,
            id=incident_id,
            body={
                "script": {
                    "source": _UPSERT_SCRIPT,
                    "lang": "painless",
                    "params": {"key": key, "token": token, "plaintext": plaintext},
                },
                "upsert": {
                    "incident_id": incident_id,
                    "plain_to_token": {key: token},
                    "token_to_plain": {token: plaintext},
                    "created_at": int(time.time() * 1000),
                },
            },
            retry_on_conflict=5,
        )
        return token

    async def unmask(self, incident_id: str, token: str) -> str | None:
        from elasticsearch import NotFoundError  # lazy import keeps mock tests clean

        try:
            doc = await self._es.get(index=_INDEX, id=incident_id)
            return doc["_source"].get("token_to_plain", {}).get(token)
        except NotFoundError:
            return None

    async def get_reverse_map(self, incident_id: str) -> dict[str, str]:
        from elasticsearch import NotFoundError

        try:
            doc = await self._es.get(index=_INDEX, id=incident_id)
            return dict(doc["_source"].get("token_to_plain", {}))
        except NotFoundError:
            return {}

    async def delete_map(self, incident_id: str) -> None:
        from elasticsearch import NotFoundError

        try:
            await self._es.delete(index=_INDEX, id=incident_id)
        except NotFoundError:
            pass
