"""
FileRecord
──────────
DICL 의 모든 발견 결과는 단일 FileRecord 형태로 표준화된다.
백서 3.4 Unified Record 원칙: 별도 SiteRecord 를 만들지 않는다.
"""

from __future__ import annotations

import uuid
import time

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


@dataclass
class FileRecord:
    """
    DICL 의 통일 출력 단위.

    type 은 다음 중 하나의 값을 가진다.
        - "site"   : 사이트 자체
        - "video"  : 동영상 리소스
        - "image"  : 이미지 리소스
        - "audio"  : 오디오 리소스
        - "pdf"    : PDF 문서 리소스
        - "url"    : 일반 URL (참고용)
        - "api"    : API endpoint
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = "url"
    path: Optional[str] = None
    meta: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    # ── factory ────────────────────────────────────────────
    @classmethod
    def create(
        cls,
        type: str,
        path: Optional[str] = None,
        meta: Optional[dict] = None,
    ) -> "FileRecord":
        return cls(
            type=type,
            path=path,
            meta=meta or {},
        )

    # ── helpers ────────────────────────────────────────────
    def to_dict(self) -> dict:
        return asdict(self)

    def __repr__(self) -> str:
        url = (self.meta.get("fields") or {}).get("url") or self.path or ""
        return f"<FileRecord type={self.type!r} url={url!r}>"
