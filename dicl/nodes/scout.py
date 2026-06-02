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

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from ..core.node import Node, Payload


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; DICL/2.0; "
        "+https://dlegoream.lab/dicl)"
    )
}


class ScoutNode(Node):
    name = "ScoutNode"

    def __init__(self, timeout: float = 10.0) -> None:
        self.timeout = timeout

    # ──────────────────────────────────────────────────────
    def process(self, payload: Payload) -> Payload:
        resp = requests.get(
            payload.url,
            timeout=self.timeout,
            headers=DEFAULT_HEADERS,
            allow_redirects=True,
        )

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
