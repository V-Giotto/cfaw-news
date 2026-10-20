"""One canonical text convention; file integrity always hashes original bytes."""

import hashlib
import json
import unicodedata


def normalize_text(value: str) -> str:
    return unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


def visible_text(title: str, text_excerpt: str | None, paragraphs) -> str:
    # Preserve empty slots and duplicate excerpts: the exact sequence is the contract.
    parts = [title, text_excerpt or "", *(p.text for p in paragraphs)]
    return "\n\n".join(normalize_text(part) for part in parts)


def content_sha256(title: str, text_excerpt: str | None, paragraphs) -> str | None:
    if not text_excerpt and not paragraphs:
        return None  # A metadata title is discovery, not a body of evidence.
    return sha256_bytes(visible_text(title, text_excerpt, paragraphs).encode("utf-8"))
