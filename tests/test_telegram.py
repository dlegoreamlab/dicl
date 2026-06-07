from __future__ import annotations

from datetime import datetime, timezone

from dicl.telegram import TelethonTelegramCollector


class DummyFile:
    def __init__(self, *, name=None, size=None, duration=None):
        self.name = name
        self.size = size
        self.duration = duration


class DummyPhotoSize:
    def __init__(self, w: int, h: int):
        self.w = w
        self.h = h


class DummyPhoto:
    def __init__(self, sizes):
        self.sizes = sizes


class DummyDocument:
    def __init__(self, *, mime_type=None, size=None, attributes=None):
        self.mime_type = mime_type
        self.size = size
        self.attributes = attributes or []


class DocumentAttributeFilename:
    def __init__(self, file_name: str):
        self.file_name = file_name


class DocumentAttributeVideo:
    def __init__(self, *, duration=0, w=0, h=0):
        self.duration = duration
        self.w = w
        self.h = h


class DocumentAttributeAudio:
    def __init__(self, *, duration=0, voice=False, performer=None, title=None):
        self.duration = duration
        self.voice = voice
        self.performer = performer
        self.title = title


class DummyChat:
    def __init__(self, *, chat_id: int, username: str | None = None):
        self.id = chat_id
        self.username = username


class DummyMessage:
    def __init__(
        self,
        *,
        message_id: int,
        chat_id: int,
        text: str = "",
        date: datetime | None = None,
        photo=None,
        document=None,
        file=None,
        grouped_id=None,
        media=None,
    ):
        self.id = message_id
        self.chat_id = chat_id
        self.message = text
        self.date = date or datetime.now(timezone.utc)
        self.photo = photo
        self.document = document
        self.file = file
        self.grouped_id = grouped_id
        self.media = media


def test_telegram_photo_is_normalized_to_dfss_image() -> None:
    collector = TelethonTelegramCollector(api_id=1, api_hash="hash")
    chat = DummyChat(chat_id=-100123456, username="demo_channel")
    msg = DummyMessage(
        message_id=77,
        chat_id=chat.id,
        text="cover image",
        photo=DummyPhoto([DummyPhotoSize(320, 180), DummyPhotoSize(1280, 720)]),
        file=DummyFile(size=2048),
    )

    normalized = collector.normalize_message(msg, chat=chat)
    record = collector.file_record_from_message(msg, chat=chat, normalized=normalized)

    assert normalized["record_type"] == "image"
    assert normalized["permalink"] == "https://t.me/demo_channel/77"
    assert record is not None
    assert record.type == "image"
    assert record.meta["relation"] == {
        "platform": "telegram",
        "chat_id": -100123456,
        "message_id": 77,
    }
    assert record.meta["fields"]["width"] == 1280
    assert record.meta["fields"]["height"] == 720
    assert record.validate() is True


def test_telegram_voice_message_is_normalized_to_dfss_audio() -> None:
    collector = TelethonTelegramCollector(api_id=1, api_hash="hash")
    msg = DummyMessage(
        message_id=88,
        chat_id=-100222333,
        text="voice note",
        document=DummyDocument(
            mime_type="audio/ogg",
            size=4096,
            attributes=[
                DocumentAttributeAudio(duration=12, voice=True),
                DocumentAttributeFilename("voice.ogg"),
            ],
        ),
    )

    normalized = collector.normalize_message(msg)
    record = collector.file_record_from_message(msg, normalized=normalized)

    assert normalized["record_type"] == "audio"
    assert record is not None
    assert record.type == "audio"
    assert record.meta["relation"]["platform"] == "telegram"
    assert record.meta["relation"]["chat_id"] == -100222333
    assert record.meta["relation"]["message_id"] == 88
    assert record.meta["fields"]["file_name"] == "voice.ogg"
    assert record.validate() is True


def test_telegram_music_and_pdf_are_both_supported() -> None:
    collector = TelethonTelegramCollector(api_id=1, api_hash="hash")

    music_msg = DummyMessage(
        message_id=91,
        chat_id=-100999111,
        text="single release",
        document=DummyDocument(
            mime_type="audio/mpeg",
            size=8192,
            attributes=[
                DocumentAttributeAudio(duration=180, performer="DFSS", title="Track One"),
                DocumentAttributeFilename("track-one.mp3"),
            ],
        ),
    )
    pdf_msg = DummyMessage(
        message_id=92,
        chat_id=-100999111,
        text="whitepaper",
        document=DummyDocument(
            mime_type="application/pdf",
            size=16384,
            attributes=[DocumentAttributeFilename("spec.pdf")],
        ),
    )

    music_record = collector.file_record_from_message(music_msg)
    pdf_record = collector.file_record_from_message(pdf_msg)

    assert music_record is not None
    assert music_record.type == "music"
    assert music_record.meta["fields"]["artist"] == "DFSS"
    assert music_record.validate() is True

    assert pdf_record is not None
    assert pdf_record.type == "pdf"
    assert pdf_record.meta["fields"]["file_name"] == "spec.pdf"
    assert pdf_record.meta["relation"]["message_id"] == 92
    assert pdf_record.validate() is True
