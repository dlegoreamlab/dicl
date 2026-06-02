"""
Node 추상 클래스
────────────────
백서 §8 Central Intelligent Crawl Control System 의 노드 모델:

    Scout Node  →  Control Node  →  Heavy Analyzer

모든 노드는 process(payload) → payload 형태로 데이터를 흘려보낸다.
이로써 노드를 자유롭게 조립/대체할 수 있다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Payload:
    """
    노드 사이를 흐르는 데이터 패킷.
    """
    url: str
    depth: int = 0
    html: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    status_code: int | None = None
    # Scout 가 발견한 후보 미디어 링크 (분류 전)
    candidates: list[str] = field(default_factory=list)
    # Control 이 평가한 우선순위 점수
    priority: float = 0.0
    # Heavy 가 추가한 동적 발견 결과
    dynamic_media: list[str] = field(default_factory=list)
    # 노드 간 자유 메타
    extras: dict[str, Any] = field(default_factory=dict)


class Node(ABC):
    """모든 노드의 부모. 단일 책임 단위."""

    name: str = "Node"

    @abstractmethod
    def process(self, payload: Payload) -> Payload:
        """payload 를 받아 가공 후 반환한다."""
        raise NotImplementedError
