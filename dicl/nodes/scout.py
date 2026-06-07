"""
Scout Node (백서 §8)
────────────────────
역할
    • HTTP GET 으로 HTML 수집
    • <img>, <video>, <audio>, <source>, <a href> 태그에서 미디어 후보 URL 수집
    • Heavy Analyzer 가 필요할지 가벼운 휴리스틱으로 판단

Scout 는 *가볍게* 동작한다. JS 렌더링은 하지 않는다.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError, Timeout

from ..core.node import Node, Payload


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; DICL/2.0; "
        "+https://dlegoream.lab/dicl)"
    )
}


class ScoutNode(Node):
    name = "ScoutNode"

    def __init__(
        self,
        timeout: float = 10.0,
        *,
        max_retries: int = 3,
        backoff_factor: float = 1.0,
        retry_statuses: tuple[int, ...] = (429, 500, 502, 503, 504),
        sleep_func=None,
    ) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.retry_statuses = retry_statuses
        self.sleep_func = sleep_func or time.sleep

    # ──────────────────────────────────────────────────────
    def process(self, payload: Payload) -> Payload:
        resp = self._get_with_retry(payload.url, payload)

        payload.html = resp.text
        payload.status_code = resp.status_code
        payload.headers = dict(resp.headers)

        soup = BeautifulSoup(resp.text, "html.parser")
        payload.candidates = self._collect_candidates(soup, payload.url)

        # SPA 휴리스틱: 본문이 짧고 <script> 가 많으면 Heavy 가 필요
        scripts = soup.find_all("script")
        body_text = soup.get_text(strip=True)
        payload.extras["needs_heavy"] = (
            len(scripts) > 5 and len(body_text) < 500
        )

        return payload

    def _get_with_retry(self, url: str, payload: Payload):
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                resp = requests.get(
                    url,
                    timeout=self.timeout,
                    headers=DEFAULT_HEADERS,
                    allow_redirects=True,
                )
            except (Timeout, RequestsConnectionError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    self._log_failed_url(
                        payload,
                        url=url,
                        error_type=type(exc).__name__,
                        retry_count=attempt,
                    )
                    raise
                self._sleep_before_retry(attempt)
                continue

            if resp.status_code in self.retry_statuses:
                last_error = HTTPError(
                    f"Retry exhausted for {url}: HTTP {resp.status_code}",
                    response=resp,
                )
                if attempt >= self.max_retries:
                    self._log_failed_url(
                        payload,
                        url=url,
                        error_type=f"HTTP {resp.status_code}",
                        retry_count=attempt,
                    )
                    raise last_error
                self._sleep_before_retry(attempt)
                continue

            return resp

        if last_error is not None:
            raise last_error
        raise RuntimeError(f"Retry loop exhausted unexpectedly for URL: {url}")

    def _sleep_before_retry(self, attempt: int) -> None:
        delay = self.backoff_factor * (2 ** attempt)
        self.sleep_func(delay)

    @staticmethod
    def _log_failed_url(
        payload: Payload,
        *,
        url: str,
        error_type: str,
        retry_count: int,
    ) -> None:
        payload.extras.setdefault("failed_url_logs", []).append(
            {
                "url": url,
                "error_type": error_type,
                "occurred_at": datetime.now(timezone.utc)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
                "retry_count": retry_count,
            }
        )

    # ──────────────────────────────────────────────────────
    def _collect_candidates(self, soup: BeautifulSoup, base: str) -> list[str]:
        found: list[str] = []

        # 1) <img>
        for tag in soup.find_all("img"):
            for attr in ("src", "data-src", "data-original"):
                v = tag.get(attr)
                if v:
                    found.append(urljoin(base, v))

        # 2) <video> / <audio> 및 그 안의 <source>
        for tag in soup.find_all(["video", "audio"]):
            v = tag.get("src")
            if v:
                found.append(urljoin(base, v))
            for src in tag.find_all("source"):
                v = src.get("src")
                if v:
                    found.append(urljoin(base, v))

        # 3) <a href> — PDF / 다운로드 링크 회수용
        for tag in soup.find_all("a"):
            v = tag.get("href")
            if v:
                found.append(urljoin(base, v))

        # 4) <link rel="...icon..."> / og:image 등 메타 이미지
        for tag in soup.find_all("meta"):
            prop = (tag.get("property") or tag.get("name") or "").lower()
            if prop in ("og:image", "twitter:image"):
                v = tag.get("content")
                if v:
                    found.append(urljoin(base, v))

        # 중복 제거 (순서 유지)
        seen, out = set(), []
        for u in found:
            if u not in seen:
                seen.add(u)
                out.append(u)
        return out
