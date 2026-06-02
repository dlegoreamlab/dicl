"""
Relationship Engine + Observed Sitemap (백서 §7, §11)
─────────────────────────────────────────────────────
역할
    • Site ↔ Media 의 관계 그래프 생성
    • Accumulated Structural Knowledge 형태의 Observed Sitemap 갱신
"""

from __future__ import annotations

from collections import defaultdict
from urllib.parse import urlparse


class RelationshipEngine:
    name = "RelationshipEngine"

    def __init__(self) -> None:
        # site_url → {media_type → [media_url, ...]}
        self._graph: dict[str, dict[str, list[str]]] = defaultdict(
            lambda: defaultdict(list)
        )

    def link(self, site_url: str, discoveries: list[dict]) -> None:
        for d in discoveries:
            self._graph[site_url][d["media_type"]].append(d["url"])

    # ── Observed Sitemap ──────────────────────────────────
    def observed_sitemap(self) -> dict:
        """
        백서 §11 의 예시 구조:

            Site
            ├─ Media
            │   ├─ Image
            │   ├─ Audio
            │   └─ Video
            └─ Document
        """
        sitemap: dict = {}
        for site, buckets in self._graph.items():
            sitemap[site] = {
                "domain": urlparse(site).netloc,
                "media": {
                    "image": list(set(buckets.get("image", []))),
                    "video": list(set(buckets.get("video", []))),
                    "audio": list(set(buckets.get("audio", []))),
                },
                "document": {
                    "pdf": list(set(buckets.get("pdf", []))),
                },
            }
        return sitemap

    def relations(self, site_url: str) -> list[dict]:
        out: list[dict] = []
        for media_type, urls in self._graph.get(site_url, {}).items():
            for u in urls:
                out.append(
                    {"from": site_url, "to": u, "type": media_type}
                )
        return out
