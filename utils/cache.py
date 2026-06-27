import asyncio
from functools import partial
from pathlib import Path

import diskcache

CACHE_DIR = Path(__file__).resolve().parent.parent / ".osint_cache"


class AsyncOSINTCache:
    def __init__(self, cache_dir: Path = CACHE_DIR):
        self._cache = diskcache.Cache(str(cache_dir))

    async def get(self, key: str):
        loop = asyncio.get_event_loop()
        value = await loop.run_in_executor(None, self._cache.get, key)
        return value

    async def set(self, key: str, value, expire: int = 3600) -> None:
        loop = asyncio.get_event_loop()
        fn = partial(self._cache.set, key, value, expire=expire)
        await loop.run_in_executor(None, fn)

    async def delete(self, key: str) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._cache.delete, key)

    def close(self) -> None:
        self._cache.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.close()
