"""Unit tests for the Masker — no external dependencies."""

import pytest

from app.masker import ElasticsearchMasker, Masker


# ---------------------------------------------------------------------------
# In-memory Masker (existing tests, unchanged)
# ---------------------------------------------------------------------------

def test_mask_returns_stable_token():
    m = Masker()
    t1 = m.mask("inc-1", "user", "john.doe")
    t2 = m.mask("inc-1", "user", "john.doe")
    assert t1 == t2


def test_different_incidents_produce_different_tokens():
    m = Masker()
    t1 = m.mask("inc-1", "user", "john.doe")
    t2 = m.mask("inc-2", "user", "john.doe")
    assert t1 != t2


def test_unmask_round_trip():
    m = Masker()
    plaintext = "192.168.1.100"
    token = m.mask("inc-3", "ip", plaintext)
    assert m.unmask("inc-3", token) == plaintext


def test_unmask_unknown_token_returns_none():
    m = Masker()
    assert m.unmask("inc-x", "nosuchtoken") is None


def test_delete_map_clears_reverse_map():
    m = Masker()
    token = m.mask("inc-4", "host", "dc01.corp")
    m.delete_map("inc-4")
    assert m.unmask("inc-4", token) is None


def test_token_prefix_by_kind():
    m = Masker()
    assert m.mask("inc-5", "user", "alice").startswith("user_")
    assert m.mask("inc-5", "host", "server1").startswith("host_")
    assert m.mask("inc-5", "ip", "10.0.0.1").startswith("ip_")


def test_empty_plaintext_passthrough():
    m = Masker()
    assert m.mask("inc-6", "user", "") == ""


# ---------------------------------------------------------------------------
# ElasticsearchMasker — tested with an AsyncMock ES client
# ---------------------------------------------------------------------------

class _FakeES:
    """Minimal fake AsyncElasticsearch that stores docs in memory."""

    def __init__(self) -> None:
        self._docs: dict[str, dict] = {}
        self.indices = _FakeIndices(self._docs)

    async def update(self, *, index: str, id: str, body: dict, retry_on_conflict: int = 0) -> None:
        doc = self._docs.get(id)
        if doc is None:
            # upsert path
            self._docs[id] = dict(body["upsert"])
        else:
            # script path: apply the same logic as the Painless script
            params = body["script"]["params"]
            key, token, plaintext = params["key"], params["token"], params["plaintext"]
            if key not in doc.get("plain_to_token", {}):
                doc.setdefault("plain_to_token", {})[key] = token
                doc.setdefault("token_to_plain", {})[token] = plaintext

    async def get(self, *, index: str, id: str) -> dict:
        from elasticsearch import NotFoundError
        if id not in self._docs:
            raise NotFoundError(404, {}, {})
        return {"_source": self._docs[id]}

    async def delete(self, *, index: str, id: str) -> None:
        from elasticsearch import NotFoundError
        if id not in self._docs:
            raise NotFoundError(404, {}, {})
        del self._docs[id]


class _FakeIndices:
    def __init__(self, docs: dict) -> None:
        self._docs = docs
        self._created: set[str] = set()

    async def exists(self, *, index: str) -> bool:
        return index in self._created

    async def create(self, *, index: str, body: dict) -> None:
        self._created.add(index)


@pytest.fixture
def es_masker():
    return ElasticsearchMasker(_FakeES())


@pytest.mark.asyncio
async def test_es_mask_returns_stable_token(es_masker):
    t1 = await es_masker.mask("inc-1", "user", "alice")
    t2 = await es_masker.mask("inc-1", "user", "alice")
    assert t1 == t2
    assert t1.startswith("user_")


@pytest.mark.asyncio
async def test_es_different_incidents_different_tokens(es_masker):
    t1 = await es_masker.mask("inc-1", "user", "alice")
    t2 = await es_masker.mask("inc-2", "user", "alice")
    assert t1 != t2


@pytest.mark.asyncio
async def test_es_unmask_round_trip(es_masker):
    plaintext = "192.168.0.1"
    token = await es_masker.mask("inc-3", "ip", plaintext)
    result = await es_masker.unmask("inc-3", token)
    assert result == plaintext


@pytest.mark.asyncio
async def test_es_unmask_unknown_returns_none(es_masker):
    assert await es_masker.unmask("inc-x", "nosuchtoken") is None


@pytest.mark.asyncio
async def test_es_delete_map_clears(es_masker):
    token = await es_masker.mask("inc-4", "host", "dc01.corp")
    await es_masker.delete_map("inc-4")
    assert await es_masker.unmask("inc-4", token) is None


@pytest.mark.asyncio
async def test_es_empty_plaintext_passthrough(es_masker):
    assert await es_masker.mask("inc-5", "user", "") == ""


@pytest.mark.asyncio
async def test_es_ensure_index_idempotent(es_masker):
    await es_masker.ensure_index()
    await es_masker.ensure_index()  # second call must not raise
