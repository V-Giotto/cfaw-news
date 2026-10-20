from types import SimpleNamespace

import pytest

from evals.intelligence_v1.hashing import content_sha256, normalize_text, sha256_bytes, visible_text


def test_nfc_lf_without_trim_or_truncation():
    assert normalize_text(" e\u0301\r\ntext\r ") == " é\ntext\n "
    p1 = (SimpleNamespace(text="e\u0301\r\n"),)
    p2 = (SimpleNamespace(text="é\n"),)
    assert content_sha256("title", "", p1) == content_sha256("title", "", p2)
    assert content_sha256("title", "", p2) != content_sha256("title ", "", p2)
    assert visible_text("title", "", p2) == "title\n\n\n\né\n"
    assert sha256_bytes(b"a\r\n") != sha256_bytes(b"a\n")
    assert content_sha256("metadata title", None, ()) is None


@pytest.mark.parametrize("field", ["title", "text_excerpt", "paragraphs"])
def test_HASH01_visible_text_change_rejects_stale_sha(edit, field):
    from evals.intelligence_v1.validate import validate_dataset

    changed = [{"paragraph_id": "p1", "text": "altered"}] if field == "paragraphs" else "altered"
    report = validate_dataset(edit("documents.jsonl", 0, **{field: changed}), strict=False)
    assert any(x.code == "SHA_MISMATCH" and x.field == "content_sha256" for x in report.errors)
