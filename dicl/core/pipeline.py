"""
Pipeline
────────
노드를 순서대로 실행하는 단순 컨테이너.
백서 §4 시스템 구조의 흐름을 그대로 표현한다.
"""

from __future__ import annotations

from .node import Node, Payload


class Pipeline:
    def __init__(self, nodes: list[Node]) -> None:
        self.nodes = nodes

    def run(self, payload: Payload) -> Payload:
        for node in self.nodes:
            try:
                payload = node.process(payload)
            except Exception as e:                              # noqa: BLE001
                # 노드 실패가 전체 파이프라인을 중단시키지 않도록 격리한다.
                payload.extras.setdefault("errors", []).append(
                    {"node": node.name, "error": repr(e)}
                )
        return payload
