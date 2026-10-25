import pytest

from evals.intelligence_g2.contracts import json_bytes
from evals.intelligence_g2.pr6.manifest import finish, pinned, sealed, sha256_bytes, source_release
from evals.intelligence_v1.exceptions import ContractError

from ..support import output_path


def test_current_uncommitted_source_cannot_be_final_accepted():
    # A non-existent commit can never become a final release, even in a future clean checkout.
    with pytest.raises(ContractError) as e:
        source_release("0" * 40)
    assert e.value.code == "G2_PR6_SOURCE_NOT_COMMITTED"


def test_seal_detects_partial_unknown_or_changed_artifacts():
    out = output_path()
    out.mkdir(parents=True)
    pin = finish(out, {"safe.json": json_bytes({"status": "data"})}, {"role": "unit"})
    assert sealed(out, pin)["role"] == "unit"
    (out / "extra.txt").write_text("unlisted", encoding="utf-8")
    with pytest.raises(ContractError) as e:
        sealed(out, pin)
    assert e.value.code == "SHA_MISMATCH" and e.value.field == "artifact_set"
    (out / "extra.txt").unlink()
    (out / "safe.json").write_bytes(b"{}")
    with pytest.raises(ContractError) as e:
        sealed(out, pin)
    assert e.value.code == "SHA_MISMATCH"


def test_external_pin_is_not_silently_refreshed():
    out = output_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b"a")
    pin = sha256_bytes(out.read_bytes())
    out.write_bytes(b"b")
    with pytest.raises(ContractError) as e:
        pinned(out, pin)
    assert e.value.code == "SHA_MISMATCH"


def test_unsealed_output_never_becomes_acceptance():
    out = output_path()
    out.mkdir(parents=True)
    (out / "run_manifest.json").write_bytes(b"{}")
    with pytest.raises(ContractError) as error:
        sealed(out, sha256_bytes(b"{}"))
    assert (error.value.code, error.value.stage, error.value.field) == (
        "G2_PR6_UNSEALED",
        "pr6",
        "sealed",
    )


def test_current_source_bytes_cannot_claim_an_old_commit(monkeypatch):
    import evals.intelligence_g2.pr6.manifest as module

    monkeypatch.setattr(module, "fingerprints", lambda: {"evals/new.py": sha256_bytes(b"new")})
    monkeypatch.setattr(
        module,
        "git",
        lambda *args: ("a" * 40).encode() if args == ("rev-parse", "HEAD") else b"old",
    )
    with pytest.raises(ContractError) as error:
        source_release("a" * 40)
    assert (error.value.code, error.value.stage, error.value.field) == (
        "G2_PR6_SOURCE_NOT_COMMITTED",
        "pr6",
        "source_files",
    )
