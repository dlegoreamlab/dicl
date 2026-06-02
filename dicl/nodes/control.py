"""
Control Node (백서 §8, §9)
─────────────────────────
역할
    • Scout 가 수집한 후보들의 중요도 계산
    • Heavy Analyzer 호출 여부 결정
    • 우선순위 점수를 Payload.priority 에 기록

평가 요소 (백서 §9)
    • 정보 가치     : 미디어 4종 매칭 개수
    • 콘텐츠 품질   : HTTP status, HTML 길이
    • 도메인 신뢰도 : (확장 가능) — 현재는 무가중치
"""

from __future__ import annotations

from ..core.node import Node, Payload
from ..utils.classifier import classify


class ControlNode(Node):
    name = "ControlNode"

    def process(self, payload: Payload) -> Payload:
        media_hits = sum(
            1 for u in payload.candidates if classify(u) is not None
        )

        # 단순하지만 명시적인 점수 모델
        score = 0.0
        if payload.status_code and 200 <= payload.status_code < 300:
            score += 1.0
        score += min(media_hits / 10.0, 5.0)            # 미디어가 많을수록 가점
        if payload.html:
            score += min(len(payload.html) / 50_000, 1.0)

        payload.priority = round(score, 3)

        # Heavy 호출 결정 (Scout 의 휴리스틱 + 미디어 0건일 때)
        payload.extras["dispatch_heavy"] = (
            payload.extras.get("needs_heavy", False) or media_hits == 0
        )

        return payload
