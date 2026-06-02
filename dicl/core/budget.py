"""
Visit Budget System (백서 §10)
─────────────────────────────
무한 탐색 방지, 자원 절약, 도메인 균형 유지를 위한 예산 관리자.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from urllib.parse import urlparse


@dataclass
class VisitBudget:
    max_depth: int = 2
    max_visits: int = 200
    max_per_domain: int = 80
    max_seconds: float = 60.0

    _visits: int = 0
    _started_at: float = field(default_factory=time.time)
    _per_domain: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    _seen: set[str] = field(default_factory=set)

    # ── checks ─────────────────────────────────────────────
    def can_visit(self, url: str, depth: int) -> bool:
        if url in self._seen:
            return False
        if depth > self.max_depth:
            return False
        if self._visits >= self.max_visits:
            return False
        if time.time() - self._started_at > self.max_seconds:
            return False
        if self._per_domain[urlparse(url).netloc] >= self.max_per_domain:
            return False
        return True

    def register(self, url: str) -> None:
        self._seen.add(url)
        self._visits += 1
        self._per_domain[urlparse(url).netloc] += 1

    # ── stats ──────────────────────────────────────────────
    def stats(self) -> dict:
        return {
            "visits": self._visits,
            "elapsed": round(time.time() - self._started_at, 2),
            "domains": dict(self._per_domain),
        }
