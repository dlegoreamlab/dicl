"""
Analysis Engine (백서 §6)
─────────────────────────
역할
    • 기술 스택 추정
    • 인증 방식 추정
    • 사이트 도메인 특성 요약
"""

from __future__ import annotations

import re
from bs4 import BeautifulSoup

from ..core.node import Payload


_FRAMEWORK_HINTS: dict[str, re.Pattern[str]] = {
    "react":     re.compile(r"__REACT_DEVTOOLS_GLOBAL_HOOK__|data-reactroot|react(\.|-)\w*\.js", re.I),
    "vue":       re.compile(r"__VUE__|data-v-[0-9a-f]{6,}|vue(\.|-)\w*\.js", re.I),
    "angular":   re.compile(r"ng-version=|angular(\.|-)\w*\.js", re.I),
    "next.js":   re.compile(r"/_next/", re.I),
    "nuxt":      re.compile(r"__NUXT__|/_nuxt/", re.I),
    "svelte":    re.compile(r"svelte(-|/)", re.I),
    "wordpress": re.compile(r"/wp-content/|/wp-includes/", re.I),
}


class AnalysisEngine:
    name = "AnalysisEngine"

    def analyze(self, payload: Payload) -> dict:
        html = payload.html or ""
        soup = BeautifulSoup(html, "html.parser") if html else None

        framework = self._detect_framework(html)
        auth_type = self._detect_auth(html)

        title = None
        language = None
        if soup:
            if soup.title and soup.title.string:
                title = soup.title.string.strip()
            if soup.html:
                language = soup.html.get("lang")

        return {
            "title": title,
            "language": language,
            "framework": framework,
            "server": payload.headers.get("Server"),
            "auth_type": auth_type,
            "status_code": payload.status_code,
        }

    # ── helpers ───────────────────────────────────────────
    def _detect_framework(self, html: str) -> str | None:
        for name, pattern in _FRAMEWORK_HINTS.items():
            if pattern.search(html):
                return name
        return None

    def _detect_auth(self, html: str) -> str:
        lower = html.lower()
        if "bearer " in lower or "jwt" in lower:
            return "jwt"
        if 'type="password"' in lower or "login" in lower:
            return "form"
        return "none"
