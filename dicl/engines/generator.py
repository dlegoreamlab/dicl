"""
FileRecord Generator (백서 §12)
───────────────────────────────
모든 발견 결과(사이트, 미디어)를 통일된 FileRecord 로 변환한다.
"""

from __future__ import annotations

import time
from urllib.parse import urlparse

from ..records.file_record import FileRecord


class FileRecordGenerator:
    name = "FileRecordGenerator"

    # ── Site Record ───────────────────────────────────────
    def make_site_record(
        self,
        site_url: str,
        analysis: dict,
        discoveries: list[dict],
        relations: list[dict],
        observed_sitemap: dict,
    ) -> FileRecord:

        media_count = sum(1 for d in discoveries if d["media_type"] != "pdf")
        pdf_count = sum(1 for d in discoveries if d["media_type"] == "pdf")
        now = time.time()

        return FileRecord.create(
            type="site",
            path=None,
            meta={
                "fields": {
                    "url": site_url,
                    "domain": urlparse(site_url).netloc,
                    "title": analysis.get("title"),
                    "language": analysis.get("language"),
                    "framework": analysis.get("framework"),
                    "server": analysis.get("server"),
                    "status_code": analysis.get("status_code"),
                    "site_type": None,
                    "created_at": None,
                    "crawled_at": now,
                    "updated_at": now,
                },
                "structure": {
                    "pages": [],
                    "links": [d["url"] for d in discoveries],
                    "resources": discoveries,
                    "api_endpoints": [],
                    "media_streams": [],
                    "sitemaps": [observed_sitemap.get(site_url, {})],
                    "robots_txt": None,
                },
                "authentication": {
                    "auth_required": analysis.get("auth_type") != "none",
                    "auth_type": analysis.get("auth_type"),
                    "login_endpoint": None,
                    "session_type": None,
                },
                "media": {
                    "images": [d["url"] for d in discoveries if d["media_type"] == "image"],
                    "videos": [d["url"] for d in discoveries if d["media_type"] == "video"],
                    "audios": [d["url"] for d in discoveries if d["media_type"] == "audio"],
                    "documents": [d["url"] for d in discoveries if d["media_type"] == "pdf"],
                },
                "semantic": {
                    "topics": [],
                    "keywords": [],
                    "entities": [],
                    "summary": None,
                    "embedding": None,
                },
                "relations": {
                    "outbound_links": [r["to"] for r in relations],
                    "inbound_links": [],
                    "api_relations": [],
                    "media_relations": relations,
                    "related_records": [],
                },
                "analysis": {
                    "technology_stack": [analysis.get("framework")] if analysis.get("framework") else [],
                    "content_category": None,
                    "crawl_depth": 0,
                    "api_count": 0,
                    "media_count": media_count,
                    "document_count": pdf_count,
                    "link_count": len(discoveries),
                },
                "scoring": {
                    "importance_score": 0,
                    "quality_score": 0,
                    "freshness_score": 0,
                    "authority_score": 0,
                },
            },
        )

    # ── Media Record ──────────────────────────────────────
    def make_media_record(self, parent_url: str, discovery: dict) -> FileRecord:
        url = discovery["url"]
        return FileRecord.create(
            type=discovery["media_type"],          # "video" / "image" / "audio" / "pdf"
            path=url,
            meta={
                "fields": {
                    "url": url,
                    "domain": discovery["domain"],
                    "parent_site": parent_url,
                    "media_type": discovery["media_type"],
                    "crawled_at": time.time(),
                },
                "relations": {
                    "inbound_links": [parent_url],
                    "outbound_links": [],
                },
            },
        )
