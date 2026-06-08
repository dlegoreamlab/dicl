from __future__ import annotations

import asyncio
import mimetypes
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from dfss.schemas.audio import build_audio_record
from dfss.schemas.image import build_image_record
from dfss.schemas.music import build_music_record
from dfss.schemas.pdf import build_pdf_record
from dfss.schemas.video import build_video_record

from ..records.file_record import FileRecord


@dataclass
class TelegramCollectResult:
    normalized_messages: list[dict[str, Any]] = field(default_factory=list)
    media_records: list[FileRecord] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)


class TelethonTelegramCollector:
    """Collect Telegram messages via Telethon and normalize media into DFSS records."""

    def __init__(self, api_id: int, api_hash: str, *, session: str = "dicl_telegram") -> None:
        self.api_id = api_id
        self.api_hash = api_hash
        self.session = session

    def collect(
        self,
        entity: str | int,
        *,
        limit: int = 100,
        offset_id: int = 0,
        reverse: bool = False,
    ) -> TelegramCollectResult:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.collect_async(
                    entity=entity,
                    limit=limit,
                    offset_id=offset_id,
                    reverse=reverse,
                )
            )

        raise RuntimeError(
            "collect() cannot be used inside an active event loop. Use `await collect_async(...)` instead."
        )

    async def collect_async(
        self,
        entity: str | int,
        *,
        limit: int = 100,
        offset_id: int = 0,
        reverse: bool = False,
    ) -> TelegramCollectResult:
        try:
            from telethon import TelegramClient
        except ImportError as exc:  # pragma: no cover - import guard
            raise RuntimeError(
                "telethon is not installed. Install the telegram extra first."
            ) from exc

        normalized_messages: list[dict[str, Any]] = []
        media_records: list[FileRecord] = []

        async with TelegramClient(self.session, self.api_id, self.api_hash) as client:
            chat = await client.get_entity(entity)
            async for message in client.iter_messages(
                chat,
                limit=limit,
                offset_id=offset_id,
                reverse=reverse,
            ):
                normalized = self.normalize_message(message, chat=chat)
                normalized_messages.append(normalized)
                record = self.file_record_from_message(message, chat=chat, normalized=normalized)
                if record is not None:
                    media_records.append(record)

        return TelegramCollectResult(
            normalized_messages=normalized_messages,
            media_records=media_records,
            stats={
                "entity": str(entity),
                "messages_collected": len(normalized_messages),
                "media_records": len(media_records),
                "skipped_messages": len(normalized_messages) - len(media_records),
            },
        )

    def normalize_message(self, message: Any, *, chat: Any | None = None) -> dict[str, Any]:
        chat_id = self._chat_id(message, chat)
        record_type = self._record_type(message)
        mime_type = self._mime_type(message, record_type)
        file_name = self._file_name(message, chat_id=chat_id, record_type=record_type, mime_type=mime_type)
        permalink = self._permalink(chat=chat, chat_id=chat_id, message_id=getattr(message, "id", 0))
        size = self._size(message)

        return {
            "platform": "telegram",
            "chat_id": chat_id,
            "message_id": getattr(message, "id", None),
            "grouped_id": getattr(message, "grouped_id", None),
            "date": self._iso_datetime(getattr(message, "date", None)),
            "text": getattr(message, "message", None) or "",
            "has_media": self._has_media(message),
            "record_type": record_type,
            "mime_type": mime_type,
            "file_name": file_name,
            "size": size,
            "permalink": permalink,
        }

    def file_record_from_message(
        self,
        message: Any,
        *,
        chat: Any | None = None,
        normalized: dict[str, Any] | None = None,
    ) -> FileRecord | None:
        normalized = normalized or self.normalize_message(message, chat=chat)
        record_type = normalized["record_type"]
        if record_type is None:
            return None

        relation = {
            "platform": "telegram",
            "chat_id": normalized["chat_id"],
            "message_id": normalized["message_id"],
        }
        permalink = normalized["permalink"]
        caption = normalized["text"]

        if record_type == "image":
            width, height = self._dimensions(message)
            return build_image_record(
                path=permalink,
                meta={
                    "fields": {
                        "file_name": normalized["file_name"],
                        "size": normalized["size"],
                        "mime_type": normalized["mime_type"],
                        "width": width,
                        "height": height,
                        "format": self._format_from_name(normalized["file_name"]),
                        "created_at": normalized["date"],
                    },
                    "relation": relation,
                },
            )

        if record_type == "video":
            width, height = self._dimensions(message)
            duration = self._duration(message)
            title = caption.strip() or normalized["file_name"]
            return build_video_record(
                path=permalink,
                meta={
                    "fields": {
                        "title": title,
                        "file_name": normalized["file_name"] or f"telegram_{normalized['message_id']}.mp4",
                        "size": int(normalized["size"] or 0),
                        "mime_type": normalized["mime_type"] or "video/mp4",
                        "codec": "",
                        "duration_sec": float(duration or 0.0),
                        "width": int(width or 0),
                        "height": int(height or 0),
                        "fps": 0.0,
                        "language": "",
                    },
                    "content": {
                        "transcript": "",
                        "summary": caption,
                        "captions": [],
                    },
                    "semantic": {
                        "topics": [],
                        "keywords": [],
                        "scenes": [],
                    },
                    "relation": {
                        **relation,
                        "source_url": permalink,
                        "thumbnail_path": "",
                        "chapters": [],
                    },
                    "scoring": {
                        "quality": 0.0,
                        "classification_confidence": 1.0,
                    },
                },
            )

        if record_type == "audio":
            return build_audio_record(
                path=permalink,
                meta={
                    "fields": {
                        "title": caption.strip() or normalized["file_name"],
                        "file_name": normalized["file_name"],
                        "size": normalized["size"],
                        "mime_type": normalized["mime_type"],
                        "duration_sec": self._duration(message),
                    },
                    "content": {
                        "transcript": None,
                        "summary": caption or None,
                    },
                    "relation": {
                        **relation,
                        "source_url": permalink,
                        "derived_from": None,
                        "segments": [],
                    },
                },
            )

        if record_type == "music":
            attr = self._audio_attribute(message)
            return build_music_record(
                path=permalink,
                meta={
                    "fields": {
                        "file_name": normalized["file_name"],
                        "size": normalized["size"],
                        "mime_type": normalized["mime_type"],
                        "artist": getattr(attr, "performer", None),
                        "album": None,
                        "genre": None,
                        "duration": self._duration(message),
                    },
                    "relation": relation,
                },
            )

        if record_type == "pdf":
            return build_pdf_record(
                path=permalink,
                meta={
                    "fields": {
                        "title": caption.strip() or normalized["file_name"],
                        "file_name": normalized["file_name"],
                        "size": normalized["size"],
                        "mime_type": normalized["mime_type"],
                        "source_url": permalink,
                        "snippet": caption or None,
                        "page_count": None,
                        "language": None,
                    },
                    "relation": relation,
                },
            )

        return None

    @staticmethod
    def _has_media(message: Any) -> bool:
        return bool(getattr(message, "media", None) or getattr(message, "photo", None) or getattr(message, "document", None))

    @staticmethod
    def _chat_id(message: Any, chat: Any | None) -> int | None:
        if getattr(message, "chat_id", None) is not None:
            return getattr(message, "chat_id")
        if chat is not None and getattr(chat, "id", None) is not None:
            return getattr(chat, "id")
        if getattr(message, "peer_id", None) is not None and getattr(message.peer_id, "channel_id", None) is not None:
            return getattr(message.peer_id, "channel_id")
        return None

    def _permalink(self, *, chat: Any | None, chat_id: int | None, message_id: int | None) -> str:
        username = getattr(chat, "username", None) if chat is not None else None
        if username:
            return f"https://t.me/{username}/{message_id}"
        return f"telegram://chat/{chat_id}/message/{message_id}"

    @staticmethod
    def _iso_datetime(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)

    @staticmethod
    def _document(message: Any) -> Any | None:
        if getattr(message, "document", None) is not None:
            return getattr(message, "document")
        media = getattr(message, "media", None)
        if media is not None and getattr(media, "document", None) is not None:
            return getattr(media, "document")
        return None

    def _record_type(self, message: Any) -> str | None:
        if getattr(message, "photo", None) is not None:
            return "image"

        doc = self._document(message)
        if doc is None:
            return None

        mime_type = (getattr(doc, "mime_type", None) or "").lower()
        attr_names = {attr.__class__.__name__ for attr in getattr(doc, "attributes", [])}
        audio_attr = self._audio_attribute(message)

        if mime_type == "application/pdf":
            return "pdf"
        if mime_type.startswith("image/"):
            return "image"
        if mime_type.startswith("video/") or "DocumentAttributeVideo" in attr_names:
            return "video"
        if mime_type.startswith("audio/") or audio_attr is not None:
            if audio_attr is not None and not getattr(audio_attr, "voice", False) and (
                getattr(audio_attr, "performer", None) or getattr(audio_attr, "title", None)
            ):
                return "music"
            return "audio"
        return None

    def _mime_type(self, message: Any, record_type: str | None) -> str | None:
        doc = self._document(message)
        if doc is not None and getattr(doc, "mime_type", None):
            return getattr(doc, "mime_type")
        if record_type == "image":
            return "image/jpeg"
        if record_type == "video":
            return "video/mp4"
        if record_type == "audio":
            return "audio/ogg"
        if record_type == "music":
            return "audio/mpeg"
        if record_type == "pdf":
            return "application/pdf"
        return None

    def _file_name(
        self,
        message: Any,
        *,
        chat_id: int | None,
        record_type: str | None,
        mime_type: str | None,
    ) -> str:
        file_obj = getattr(message, "file", None)
        for candidate_attr in ("name", "file_name"):
            candidate = getattr(file_obj, candidate_attr, None)
            if candidate:
                return str(candidate)

        doc = self._document(message)
        if doc is not None:
            for attr in getattr(doc, "attributes", []):
                if hasattr(attr, "file_name") and getattr(attr, "file_name"):
                    return str(getattr(attr, "file_name"))

        ext = self._extension_for_type(record_type=record_type, mime_type=mime_type)
        return f"telegram_{chat_id}_{getattr(message, 'id', 'unknown')}{ext}"

    @staticmethod
    def _size(message: Any) -> int | None:
        file_obj = getattr(message, "file", None)
        if getattr(file_obj, "size", None) is not None:
            return int(getattr(file_obj, "size"))
        doc = getattr(message, "document", None)
        if getattr(doc, "size", None) is not None:
            return int(getattr(doc, "size"))
        media_doc = getattr(getattr(message, "media", None), "document", None)
        if getattr(media_doc, "size", None) is not None:
            return int(getattr(media_doc, "size"))
        return None

    def _duration(self, message: Any) -> int | float | None:
        for attr in getattr(self._document(message), "attributes", []) or []:
            if hasattr(attr, "duration") and getattr(attr, "duration") is not None:
                return getattr(attr, "duration")
        return getattr(getattr(message, "file", None), "duration", None)

    def _dimensions(self, message: Any) -> tuple[int | None, int | None]:
        photo = getattr(message, "photo", None)
        if photo is not None:
            size = None
            for candidate in getattr(photo, "sizes", []) or []:
                if getattr(candidate, "w", None) is not None and getattr(candidate, "h", None) is not None:
                    size = candidate
            if size is not None:
                return int(getattr(size, "w")), int(getattr(size, "h"))

        for attr in getattr(self._document(message), "attributes", []) or []:
            if hasattr(attr, "w") and hasattr(attr, "h"):
                w = getattr(attr, "w", None)
                h = getattr(attr, "h", None)
                if w is not None and h is not None:
                    return int(w), int(h)
        return None, None

    def _audio_attribute(self, message: Any) -> Any | None:
        for attr in getattr(self._document(message), "attributes", []) or []:
            if attr.__class__.__name__ == "DocumentAttributeAudio":
                return attr
        return None

    @staticmethod
    def _format_from_name(name: str | None) -> str | None:
        if not name or "." not in name:
            return None
        return name.rsplit(".", 1)[-1].lower()

    def _extension_for_type(self, *, record_type: str | None, mime_type: str | None) -> str:
        guessed = mimetypes.guess_extension(mime_type or "") if mime_type else None
        if guessed == ".jpe":
            guessed = ".jpg"
        if guessed:
            return guessed
        fallback = {
            "image": ".jpg",
            "video": ".mp4",
            "audio": ".ogg",
            "music": ".mp3",
            "pdf": ".pdf",
        }
        return fallback.get(record_type, "")
