"""
DICL — Dlegoream Intelligence Crawling Library
──────────────────────────────────────────────
Web Intelligence Discovery Framework v2.0

목표
    URL 을 입력받아 동영상 / 이미지 / 오디오 / PDF 링크만을 발견하고,
    이를 통일된 FileRecord 로 변환한다.

사용법
    from dicl import DICL

    dicl = DICL()
    result = dicl.crawl("https://example.com")

    print(result.site_record)      # FileRecord(type="site")
    print(result.media_records)    # list[FileRecord]  (video/image/audio/pdf)
    print(result.observed_sitemap) # dict
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .core.node import Payload
from .core.pipeline import Pipeline
from .core.budget import VisitBudget

from .nodes.scout import ScoutNode
from .nodes.control import ControlNode
from .nodes.heavy import HeavyAnalyzerNode

from .engines.discovery import DiscoveryEngine
from .engines.analysis import AnalysisEngine
from .engines.relationship import RelationshipEngine
from .engines.generator import FileRecordGenerator

from .records.file_record import FileRecord


__version__ = "2.0.0"
__all__ = ["DICL", "CrawlResult", "FileRecord"]


@dataclass
class CrawlResult:
    site_record: FileRecord
    media_records: list[FileRecord] = field(default_factory=list)
    observed_sitemap: dict = field(default_factory=dict)
    stats: dict = field(default_factory=dict)


class DICL:
    """
    Dlegoream Intelligence Crawling Library 의 통합 Facade.
    백서 §4 시스템 구조를 그대로 코드화한다.

        URL
         ↓
        Scout  →  Control  →  Heavy
         ↓
        Discovery → Analysis → Relationship → Generator
         ↓
        FileRecord
    """

    def __init__(
        self,
        budget: VisitBudget | None = None,
        use_heavy: bool = True,
    ) -> None:
        self.budget = budget or VisitBudget()

        nodes = [ScoutNode(), ControlNode()]
        if use_heavy:
            nodes.append(HeavyAnalyzerNode())

        self.pipeline = Pipeline(nodes)
        self.discovery = DiscoveryEngine()
        self.analysis = AnalysisEngine()
        self.relationship = RelationshipEngine()
        self.generator = FileRecordGenerator()

    # ──────────────────────────────────────────────────────
    def crawl(self, url: str) -> CrawlResult:
        if not self.budget.can_visit(url, depth=0):
            raise RuntimeError(f"Budget rejects URL: {url}")
        self.budget.register(url)

        # 1) 노드 파이프라인 실행 (Scout → Control → Heavy)
        payload = Payload(url=url, depth=0)
        payload = self.pipeline.run(payload)

        # 2) Discovery: 미디어 4종만 필터링
        discoveries = self.discovery.discover(payload)

        # 3) Analysis: 사이트 메타데이터 분석
        analysis = self.analysis.analyze(payload)

        # 4) Relationship: 관계 그래프 갱신
        self.relationship.link(url, discoveries)
        relations = self.relationship.relations(url)
        observed_sitemap = self.relationship.observed_sitemap()

        # 5) FileRecord 생성
        site_record = self.generator.make_site_record(
            site_url=url,
            analysis=analysis,
            discoveries=discoveries,
            relations=relations,
            observed_sitemap=observed_sitemap,
        )
        media_records = [
            self.generator.make_media_record(url, d) for d in discoveries
        ]

        return CrawlResult(
            site_record=site_record,
            media_records=media_records,
            observed_sitemap=observed_sitemap,
            stats={
                "priority": payload.priority,
                "errors": payload.extras.get("errors", []),
                "warnings": payload.extras.get("warnings", []),
                "budget": self.budget.stats(),
            },
        )
