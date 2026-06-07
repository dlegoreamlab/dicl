"""
Discovery Engine (백서 §5)
──────────────────────────
역할
    Scout + Heavy 가 수집한 모든 후보 URL 중
    1) video / image / audio / pdf 4 가지 미디어 URL 을 추출하고
    2) 그 외 재귀 크롤링 후보 / trash URL 을 분리한다.

DFSS 자체는 건드리지 않으며, DICL 내부에서만 URL 군을 구분한다.
"""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from ..core.node import Payload
from ..utils.classifier import classify


class DiscoveryEngine:
    name = "DiscoveryEngine"

    ALLOWED = {"video", "image", "audio", "pdf"}
    NON_RECURSIVE_SUFFIXES = {
        "js", "mjs", "css", "json", "xml", "txt", "map",
        "svg", "ico", "woff", "woff2", "ttf", "eot",
        "zip", "rar", "7z", "gz", "tar", "bz2",
        "exe", "dmg", "apk", "bin",
    }

    def discover(self, payload: Payload) -> list[dict]:
        """
        반환 형식:
            [
                {"url": "...", "media_type": "video"},
                {"url": "...", "media_type": "pdf"},
                ...
            ]
        """
        seen: set[str] = set()
        results: list[dict] = []

        for url in self._iter_pool(payload):
            if not url or url in seen:
                continue
            seen.add(url)

            media_type = classify(url)
            if media_type not in self.ALLOWED:
                continue

            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                continue

            results.append(
                {
                    "url": url,
                    "media_type": media_type,
                    "domain": parsed.netloc,
                }
            )

        return results

    def discover_trash(
        self,
        payload: Payload,
        scope_domain: str | None = None,
    ) -> list[dict]:
        """
        미디어 4종이 아닌 URL 을 trash 대상으로 분리한다.
        재귀 크롤링에 사용하지 않는 자원(.js/.css 등)도 여기에 포함될 수 있다.
        """
        seen: set[str] = set()
        results: list[dict] = []

        for url in self._iter_pool(payload):
            if not url or url in seen:
                continue
            seen.add(url)

            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                continue
            if scope_domain and parsed.netloc != scope_domain:
                continue
            if url == payload.url:
                continue
            if classify(url) in self.ALLOWED:
                continue

            results.append(
                {
                    "url": url,
                    "domain": parsed.netloc,
                    "source_url": payload.url,
                }
            )

        return results

    def discover_recursive(
        self,
        payload: Payload,
        scope_domain: str | None = None,
    ) -> list[str]:
        """
        trash URL 중 실제로 재귀 크롤링을 시도할 수 있는 URL 만 선별한다.
        """
        out: list[str] = []
        for item in self.discover_trash(payload, scope_domain=scope_domain):
            url = item["url"]
            if self._is_recursive_candidate(url):
                out.append(url)
        return out

    def _iter_pool(self, payload: Payload) -> list[str]:
        pool = list(payload.candidates) + list(payload.dynamic_media)

        cleaned: list[str] = []
        for raw in pool:
            url = self._normalize_url(raw)
            if url:
                cleaned.append(url)
        return cleaned

    @staticmethod
    def _normalize_url(url: str | None) -> str | None:
        if not url:
            return None
        parsed = urlparse(url.strip())
        if not parsed.scheme:
            return None
        return urlunparse(parsed._replace(fragment=""))

    def _is_recursive_candidate(self, url: str) -> bool:
        parsed = urlparse(url)
        path = parsed.path.rsplit("/", 1)[-1]
        if "." not in path:
            return True

        suffix = path.rsplit(".", 1)[-1].lower()
        return suffix not in self.NON_RECURSIVE_SUFFIXES
