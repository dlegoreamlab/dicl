"""
Media Classifier
────────────────
DICL 은 백서 3.3 Structure Aware 에 따라 다음 4 가지 미디어만 발견 대상으로 한다.

    video / image / audio / pdf

다른 모든 링크는 무시된다. (요청 사항: "동영상 이미지 오디오 pdf 링크만 찾는")
"""

from __future__ import annotations

from urllib.parse import urlparse
import os


# 확장자 기준
VIDEO_EXT = {
    ".mp4", ".m4v", ".mov", ".avi", ".mkv", ".webm",
    ".flv", ".wmv", ".mpg", ".mpeg", ".ts", ".m3u8",
}

IMAGE_EXT = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
    ".svg", ".tif", ".tiff", ".avif", ".ico", ".heic",
}

AUDIO_EXT = {
    ".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a",
    ".wma", ".opus", ".aiff",
}

PDF_EXT = {".pdf"}


# Content-Type 기준 (백서: Heavy Analyzer 단계에서 사용 가능)
MIME_MAP: dict[str, str] = {
    "video/": "video",
    "image/": "image",
    "audio/": "audio",
    "application/pdf": "pdf",
}


def classify_by_url(url: str) -> str | None:
    """
    URL 만 보고 미디어 타입을 판별.
    매칭되지 않으면 None — 이 경우 Discovery Engine 이 폐기한다.
    """
    if not url:
        return None

    path = urlparse(url).path.lower()
    ext = os.path.splitext(path)[1]

    if ext in VIDEO_EXT:
        return "video"
    if ext in IMAGE_EXT:
        return "image"
    if ext in AUDIO_EXT:
        return "audio"
    if ext in PDF_EXT:
        return "pdf"

    return None


def classify_by_mime(content_type: str | None) -> str | None:
    if not content_type:
        return None

    content_type = content_type.lower().split(";")[0].strip()

    if content_type == "application/pdf":
        return "pdf"
    if content_type.startswith("video/"):
        return "video"
    if content_type.startswith("image/"):
        return "image"
    if content_type.startswith("audio/"):
        return "audio"

    return None


def classify(url: str, content_type: str | None = None) -> str | None:
    """
    URL 우선, Content-Type 보조로 분류한다.
    """
    return classify_by_url(url) or classify_by_mime(content_type)
