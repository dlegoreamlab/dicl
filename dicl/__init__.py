"""
DICL — Dlegoream Intelligence Crawling Library
──────────────────────────────────────────────
Web Intelligence Discovery Framework v2.1

목표
    URL 을 입력받아 재귀적으로 사이트를 순회하며
    동영상 / 이미지 / 오디오 / PDF 링크를 발견하고,
    재귀 순회 과정에서 만난 비미디어 URL 은 trash record 로 분리 반환한다.

사용법
    from dicl import DICL

    dicl = DICL()
    result = dicl.crawl("https://example.com")

    print(result.site_record)       # FileRecord(type="site")
    print(result.media_records)     # list[FileRecord]  (video/image/audio/pdf)
    print(result.trash_records)     # list[FileRecord]  (url)
    print(result.observed_sitemap)  # dict
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from urllib.parse import urlparse

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
from .telegram import TelethonTelegramCollector, TelegramCollectResult


__version__ = "2.2.0"
__all__ = [
    "DICL",
    "CrawlResult",
    "TelegramCollectResult",
    "TelethonTelegramCollector",
    "FileRecord",
]


@dataclass
class CrawlResult:
    site_record: FileRecord
    media_records: list[FileRecord] = field(default_factory=list)
    trash_records: list[FileRecord] = field(default_factory=list)
    observed_sitemap: dict = field(default_factory=dict)
    stats: dict = field(default_factory=dict)

    @property
    def junk_records(self) -> list[FileRecord]:
        """Backward/semantic alias for callers preferring 'junk' terminology."""
        return self.trash_records


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

    def collect_telegram(
        self,
        *,
        api_id: int,
        api_hash: str,
        entity: str | int,
        limit: int = 100,
        session: str = "dicl_telegram",
        offset_id: int = 0,
        reverse: bool = False,
    ) -> TelegramCollectResult:
        collector = TelethonTelegramCollector(
            api_id=api_id,
            api_hash=api_hash,
            session=session,
        )
        return collector.collect(
            entity=entity,
            limit=limit,
            offset_id=offset_id,
            reverse=reverse,
        )

    # ──────────────────────────────────────────────────────
    def crawl(self, url: str) -> CrawlResult:
        root_domain = urlparse(url).netloc
        if not self.budget.can_visit(url, depth=0):
            raise RuntimeError(f"Budget rejects URL: {url}")

        queue = deque([(url, 0)])
        queued: set[str] = {url}
        visited_pages: list[str] = []

        media_map: dict[str, dict] = {}
        trash_map: dict[str, dict] = {}
        aggregated_errors: list[dict] = []
        aggregated_warnings: list[str] = []

        root_priority = 0.0
        root_analysis: dict | None = None

        while queue:
            current_url, depth = queue.popleft()
            if not self.budget.can_visit(current_url, depth=depth):
                continue

            self.budget.register(current_url)
            visited_pages.append(current_url)

            payload = Payload(url=current_url, depth=depth)
            payload = self.pipeline.run(payload)

            if depth == 0:
                root_priority = payload.priority

            aggregated_errors.extend(payload.extras.get("errors", []))
            aggregated_warnings.extend(payload.extras.get("warnings", []))

            discoveries = self.discovery.discover(payload)
            trash_urls = self.discovery.discover_trash(
                payload,
                scope_domain=root_domain,
            )
            recursive_urls = self.discovery.discover_recursive(
                payload,
                scope_domain=root_domain,
            )
            analysis = self.analysis.analyze(payload)

            if root_analysis is None:
                root_analysis = analysis

            self.relationship.link(current_url, discoveries)

            for d in discoveries:
                media_map.setdefault(
                    d["url"],
                    {
                        **d,
                        "source_url": current_url,
                        "depth": depth,
                    },
                )

            for t in trash_urls:
                if t["url"] == url:
                    continue
                trash_map.setdefault(
                    t["url"],
                    {
                        **t,
                        "source_url": current_url,
                        "depth": depth,
                    },
                )

            if depth >= self.budget.max_depth:
                continue

            for next_url in recursive_urls:
                if next_url in queued:
                    continue
                if not self.budget.can_visit(next_url, depth=depth + 1):
                    continue
                queue.append((next_url, depth + 1))
                queued.add(next_url)

        discoveries = list(media_map.values())
        trash_discoveries = list(trash_map.values())
        observed_sitemap = self.relationship.observed_sitemap()

        relations: list[dict] = []
        for page_url in visited_pages:
            relations.extend(self.relationship.relations(page_url))

        site_record = self.generator.make_site_record(
            site_url=url,
            analysis=root_analysis or {},
            discoveries=discoveries,
            relations=relations,
            observed_sitemap=observed_sitemap,
        )
        media_records = [
            self.generator.make_media_record(d.get("source_url", url), d)
            for d in discoveries
        ]
        trash_records = [
            self.generator.make_url_record(
                parent_url=t.get("source_url", url),
                url=t["url"],
            )
            for t in trash_discoveries
        ]

        return CrawlResult(
            site_record=site_record,
            media_records=media_records,
            trash_records=trash_records,
            observed_sitemap=observed_sitemap,
            stats={
                "priority": root_priority,
                "errors": aggregated_errors,
                "warnings": aggregated_warnings,
                "budget": self.budget.stats(),
                "visited_pages": visited_pages,
                "pages_crawled": len(visited_pages),
                "media_found": len(media_records),
                "trash_found": len(trash_records),
            },
        )
