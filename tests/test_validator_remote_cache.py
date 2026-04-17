import time
import unittest
from dataclasses import dataclass
from unittest.mock import AsyncMock

try:
    from scavenger.validator import KeyboxValidator, RemoteCache
except ModuleNotFoundError as exc:
    KeyboxValidator = None
    RemoteCache = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


@dataclass
class DummySettings:
    request_timeout_seconds: float = 15.0
    cache_ttl_seconds: int = 0
    network_retries: int = 0
    banned_serials_url: str = "https://example.invalid/banned.txt"
    revocation_url: str = "https://example.invalid/revocation.json"
    revocation_fallback_path: str = "res/json/status.json"
    leaked_serials_path: str = "leaks.txt"
    max_xml_size: int = 20 * 1024


@unittest.skipIf(KeyboxValidator is None, f"validator deps unavailable: {_IMPORT_ERROR}")
class ValidatorRemoteCacheTests(unittest.IsolatedAsyncioTestCase):
    def _build_settings(self) -> DummySettings:
        return DummySettings()

    async def test_fetch_banned_serials_skips_get_when_head_unchanged(self):
        validator = KeyboxValidator(self._build_settings())
        validator._banned_cache = RemoteCache(
            fetched_at=time.time() - 60,
            data=["abc"],
            etag="etag-1",
            last_modified=None,
        )
        validator._request_head_metadata = AsyncMock(return_value=("etag-1", None))
        validator._request_text = AsyncMock(side_effect=AssertionError("GET should not run"))

        result = await validator._fetch_banned_serials()

        self.assertEqual(result, ["abc"])
        validator._request_head_metadata.assert_awaited_once()
        validator._request_text.assert_not_called()

    async def test_fetch_banned_serials_fetches_when_head_changes(self):
        validator = KeyboxValidator(self._build_settings())
        validator._banned_cache = RemoteCache(
            fetched_at=time.time() - 60,
            data=["old"],
            etag="etag-old",
            last_modified=None,
        )
        validator._request_head_metadata = AsyncMock(return_value=("etag-new", None))
        validator._request_text = AsyncMock(
            return_value=("new-1\nnew-2\n", "etag-new", None)
        )

        result = await validator._fetch_banned_serials()

        self.assertEqual(result, ["new-1", "new-2"])
        validator._request_head_metadata.assert_awaited_once()
        validator._request_text.assert_awaited_once()

    async def test_load_revocation_status_skips_get_when_head_unchanged(self):
        validator = KeyboxValidator(self._build_settings())
        validator._revocation_cache = RemoteCache(
            fetched_at=time.time() - 60,
            data={"entries": {}},
            etag="rev-etag-1",
            last_modified=None,
        )
        validator._request_head_metadata = AsyncMock(return_value=("rev-etag-1", None))
        validator._request_json = AsyncMock(side_effect=AssertionError("GET should not run"))

        result = await validator._load_revocation_status()

        self.assertEqual(result, {"entries": {}})
        validator._request_head_metadata.assert_awaited_once()
        validator._request_json.assert_not_called()

    async def test_load_revocation_status_fetches_when_head_changes(self):
        validator = KeyboxValidator(self._build_settings())
        validator._revocation_cache = RemoteCache(
            fetched_at=time.time() - 60,
            data={"entries": {}},
            etag="rev-old",
            last_modified=None,
        )
        validator._request_head_metadata = AsyncMock(return_value=("rev-new", None))
        validator._request_json = AsyncMock(
            return_value=({"entries": {"abc": {"reason": "test"}}}, "rev-new", None)
        )

        result = await validator._load_revocation_status()

        self.assertIn("abc", result["entries"])
        validator._request_head_metadata.assert_awaited_once()
        validator._request_json.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
