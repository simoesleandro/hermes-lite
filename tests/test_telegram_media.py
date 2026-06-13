import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.telegram_media import default_caption, parse_pdf_message, parse_photo_message


def test_default_caption_pdf():
    msg = {"caption": "  Resuma cláusulas  "}
    assert default_caption(msg, "pdf") == "Resuma cláusulas"
    assert "documento" in default_caption({}, "pdf").lower()


def test_default_caption_photo():
    assert "treino" in default_caption({}, "photo").lower()


def test_parse_pdf_non_pdf():
    result = parse_pdf_message({"document": {"mime_type": "text/plain", "file_name": "x.txt"}})
    assert result and result.get("error")


def test_parse_pdf_rejects_non_pdf(monkeypatch):
    msg = {"document": {"mime_type": "application/pdf", "file_name": "a.pdf", "file_id": "f1"}}
    monkeypatch.setattr(
        "services.telegram_media.download_file_bytes",
        lambda fid: b"%PDF fake",
    )
    monkeypatch.setattr(
        "services.telegram_media.extract_pdf_text",
        lambda raw, filename: {"text": "hello", "filename": filename, "pages": 1},
    )
    result = parse_pdf_message(msg)
    assert result["text"] == "hello"


def test_parse_photo(monkeypatch):
    msg = {"photo": [{"file_id": "small", "width": 100}, {"file_id": "big", "width": 800, "file_size": 5000}]}
    monkeypatch.setattr("services.telegram_media.download_file_bytes", lambda fid: b"\xff\xd8\xff")
    result = parse_photo_message(msg)
    assert result["image_b64"]
    assert result["mime"] == "image/jpeg"
