import asyncio
import pytest
import pytest_asyncio
from pathlib import Path
from utils.cache import AsyncOSINTCache


@pytest_asyncio.fixture
async def cache(tmp_path):
    async with AsyncOSINTCache(cache_dir=tmp_path / ".test_cache") as c:
        yield c


@pytest.mark.asyncio
async def test_set_and_get(cache):
    await cache.set("osint_target", "octocat_target")
    result = await cache.get("osint_target")
    assert result == "octocat_target"


@pytest.mark.asyncio
async def test_get_missing_key_returns_none(cache):
    result = await cache.get("nonexistent_key")
    assert result is None


@pytest.mark.asyncio
async def test_overwrite_value(cache):
    await cache.set("key", "valor_inicial")
    await cache.set("key", "valor_actualizado")
    result = await cache.get("key")
    assert result == "valor_actualizado"


@pytest.mark.asyncio
async def test_delete(cache):
    await cache.set("delete_me", "temporal")
    await cache.delete("delete_me")
    result = await cache.get("delete_me")
    assert result is None


@pytest.mark.asyncio
async def test_expiration(cache):
    await cache.set("expirable", "dato_osint", expire=1)

    result = await cache.get("expirable")
    assert result == "dato_osint", "El valor debe existir antes de expirar"

    await asyncio.sleep(1.5)

    result = await cache.get("expirable")
    assert result is None, "El valor debe ser None después de expirar"
