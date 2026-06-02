"""
Heavy Analyzer (백서 §8)
────────────────────────
역할
    • SPA / 동적 콘텐츠를 Playwright 로 렌더링
    • 네트워크 응답을 가로채 미디어 URL 을 보강
    • 정적 Scout 가 놓친 동영상/오디오/PDF 링크 회수

Playwright 미설치 환경에서도 깨지지 않도록 import 를 지연시킨다.
"""

from __future__ import annotations

from urllib.parse import urljoin
from bs4 import BeautifulSoup

from ..core.node import Node, Payload
from ..utils.classifier import classify


class HeavyAnalyzerNode(Node):
    name = "HeavyAnalyzerNode"

    def __init__(self, timeout_ms: int = 15000) -> None:
        self.timeout_ms = timeout_ms

    # Control 이 dispatch_heavy=True 로 표시했을 때만 동작
    def process(self, payload: Payload) -> Payload:
        if not payload.extras.get("dispatch_heavy"):
            return payload

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            payload.extras.setdefault("warnings", []).append(
                "playwright not installed; Heavy stage skipped"
            )
            return payload

        captured: list[str] = []

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                # 네트워크 응답에서 미디어 MIME 만 추출
                def _on_response(resp) -> None:
                    ctype = resp.headers.get("content-type", "")
                    if classify(resp.url, ctype):
                        captured.append(resp.url)

                page.on("response", _on_response)

                page.goto(
                    payload.url,
                    wait_until="networkidle",
                    timeout=self.timeout_ms,
                )

                html = page.content()
                browser.close()

            # 렌더링된 DOM 도 다시 한 번 파싱
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup.find_all(["img", "video", "audio", "source", "a"]):
                v = tag.get("src") or tag.get("href")
                if v:
                    captured.append(urljoin(payload.url, v))

            payload.dynamic_media = captured

        except Exception as e:                                  # noqa: BLE001
            payload.extras.setdefault("errors", []).append(
                {"node": self.name, "error": repr(e)}
            )

        return payload
