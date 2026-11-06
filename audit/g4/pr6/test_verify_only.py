"""Verify-only must not persist evidence; the formal sealing branch still must."""

import sys

import pytest

from audit.g4.pr6 import finalize as f
from audit.g4.pr6 import finalize_review as review


def reject_write(*args, **kwargs):
    pytest.fail("verify-only attempted to persist evidence")


def test_verify_controls_returns_existing_evidence_without_writing(monkeypatch):
    monkeypatch.setattr(f, "write", reject_write)
    assert f.verify_controls() == f.read(f.RUN / "control-verification.json")


def test_real_verify_only_returns_before_artifact_writers(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["finalize", "--verify-only"])
    monkeypatch.setattr(f, "write", reject_write)
    monkeypatch.setattr(review, "write", reject_write)
    monkeypatch.setattr(review, "write_new", reject_write)
    monkeypatch.setattr(review, "commands", reject_write)
    monkeypatch.setattr(review, "snapshots", reject_write)
    monkeypatch.setattr(review, "build_roots", reject_write)
    review.main()
    assert '"status": "PASS"' in capsys.readouterr().out


def test_formal_branch_persists_controls_before_sealing(monkeypatch):
    class StopAfterControlWrite(Exception):
        pass

    controls = {"status": "PASS"}

    def persist(path, value):
        assert path == review.RUN / "control-verification.json"
        assert value is controls
        raise StopAfterControlWrite

    monkeypatch.setattr(sys, "argv", ["finalize"])
    monkeypatch.setattr(f, "verify_controls", lambda: controls)
    monkeypatch.setattr(review, "write", persist)
    monkeypatch.setattr(review, "commands", reject_write)
    with pytest.raises(StopAfterControlWrite):
        review.main()
