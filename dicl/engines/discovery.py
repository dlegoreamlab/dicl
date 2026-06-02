"""
Discovery Engine (백서 §5)
──────────────────────────
역할
    Scout + Heavy 가 수집한 모든 후보 URL 중
    video / image / audio / pdf 4 가지에만 해당하는 항목을 추출한다.

이 엔진이 DICL 의 정체성을 정의한다:
    "동영상 이미지 오디오 pdf 링크만 찾는다."
"""

from __future__ import annotations

from urllib.parse import urlparse

from ..core.node import Payload
from ..utils.classifier import classify


class DiscoveryEngine:
    name = "DiscoveryEngine"

    ALLOWED = {"video", "image", "audio", "pdf"}

    def discover(self, payload: Payload) -> list[dict]:
        """
        반환 형식:
            [
                {"url": "...", "media_type": "video"},
                {"url": "...", "media_type": "pdf"},
                ...
            ]
        """
        pool = list(payload.candidates) + list(payload.dynamic_media)

        seen: set[str] = set()
        results: list[dict] = []

        for url in pool:
            if not url or url in seen:
                continue
            seen.add(url)

            media_type = classify(url)
            if media_type not in self.ALLOWED:
                continue

            # 비정상 URL 차단
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
