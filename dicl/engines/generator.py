"""
FileRecord Generator (백서 §12)
───────────────────────────────
모든 발견 결과(사이트, 미디어)를 DFSS 기반 FileRecord 로 변환한다.
"""

from __future__ import annotations

import time
from urllib.parse import urlparse

from dfss.schemas.audio import build_audio_record
from dfss.schemas.image import build_image_record
from dfss.schemas.pdf import build_pdf_record
from dfss.schemas.site import build_site_record
from dfss.schemas.video import build_video_record

from ..records.file_record import FileRecord


class FileRecordGenerator:
    name = "FileRecordGenerator"

    @staticmethod
    def _filename_from_url(url: str) -> str:
        path = urlparse(url).path.rstrip("/")
        if not path:
            return url
        return path.rsplit("/", 1)[-1] or url

    @staticmethod
    def _suffix_from_url(url: str) -> str | None:
        path = urlparse(url).path
        if "." not in path:
            return None
        return path.rsplit(".", 1)[-1].lower() or None

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

        return build_site_record(
            path=site_url,
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
                "relation": {
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
                    "importance_score": 0.0,
                    "quality_score": 0.0,
                    "freshness_score": 0.0,
                    "authority_score": 0.0,
                },
            },
        )

    # ── Media Record ──────────────────────────────────────
    def make_media_record(self, parent_url: str, discovery: dict) -> FileRecord:
        url = discovery["url"]
        media_type = discovery["media_type"]
        title = self._filename_from_url(url)
        suffix = self._suffix_from_url(url)

        if media_type == "video":
            return build_video_record(
                path=url,
                meta={
                    "fields": {"title": title},
                    "relation": {
                        "source_url": parent_url,
                        "thumbnail_path": "",
                        "chapters": [],
                    },
                },
            )

        if media_type == "audio":
            return build_audio_record(
                path=url,
                meta={
                    "fields": {"title": title},
                    "relation": {
                        "source_url": parent_url,
                        "derived_from": None,
                        "segments": [],
                    },
                },
            )

        if media_type == "image":
            return build_image_record(
                path=url,
                meta={
                    "fields": {"format": suffix},
                    "relation": {"source_url": parent_url},
                },
            )

        if media_type == "pdf":
            return build_pdf_record(
                path=url,
                meta={
                    "fields": {
                        "title": title,
                        "source_url": url,
                        "snippet": f"Discovered from {parent_url}",
                        "page_count": None,
                        "language": None,
                    },
                    "relation": {"source_url": parent_url},
                },
            )

        raise ValueError(f"Unsupported media_type: {media_type}")
