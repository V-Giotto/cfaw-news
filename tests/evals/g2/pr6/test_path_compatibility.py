from pathlib import Path

import pytest

from evals.intelligence_g2.pr6 import acceptance, checks, evaluate
from evals.intelligence_g2.pr6.manifest import ROOT, finish, sha256_bytes
from evals.intelligence_v1.exceptions import ContractError

from ..support import output_path


class BoundaryReached(Exception):
    pass


@pytest.mark.parametrize("separator", ["/", "\\"])
def test_legacy_artifact_separator_preserves_bytes_and_manifest(separator):
    root = output_path()
    target = root / "legacy-g1/primary/case/metrics.json"
    target.parent.mkdir(parents=True)
    payload = b'{"result":"fixture"}\n'
    target.write_bytes(payload)
    key = separator.join(("primary", "case", "metrics.json"))
    legacy = {"artifact_sha256": {key: sha256_bytes(payload)}}
    before = repr(legacy)
    assert checks.verify_legacy_artifacts(root, legacy) == 1
    assert repr(legacy) == before and target.read_bytes() == payload


@pytest.mark.parametrize(
    "key",
    [
        r"..\escape.json",
        r"C:\private.json",
        r"\\server\share\x",
        r"primary\..\x",
        "primary/x:stream",
        "primary//x",
    ],
)
def test_legacy_path_compatibility_does_not_allow_escape(key):
    with pytest.raises(ContractError) as error:
        checks.verify_legacy_artifacts(output_path(), {"artifact_sha256": {key: "0" * 64}})
    assert (error.value.code, error.value.stage, error.value.field) == (
        "MANIFEST_PATH_INVALID",
        "pr6",
        "path",
    )


def test_legacy_artifact_still_checks_actual_sha():
    root = output_path()
    path = root / "legacy-g1/primary/safe.json"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"{}")
    with pytest.raises(ContractError) as error:
        checks.verify_legacy_artifacts(root, {"artifact_sha256": {"primary/safe.json": "0" * 64}})
    assert (error.value.code, error.value.stage, error.value.field) == (
        "SHA_MISMATCH",
        "pr6",
        "artifact",
    )


def test_relative_evaluation_input_reaches_replay_as_absolute(monkeypatch):
    root = output_path()
    root.mkdir(parents=True)
    pin = finish(root, {"data.json": b"{}\n"}, {"role": "prediction_campaign"})

    def replay(directory, manifest):
        assert directory.is_absolute() and directory == root
        raise BoundaryReached()

    monkeypatch.setattr(evaluate, "verify_predictions", replay)
    with pytest.raises(BoundaryReached):
        evaluate.evaluate(
            root.relative_to(ROOT),
            run_manifest_sha256=pin,
            reference_manifest="unused",
            reference_sha256="0" * 64,
            out=output_path(),
        )


def test_relative_acceptance_input_reaches_seal_as_absolute(monkeypatch):
    root = output_path()

    def seal(directory, pin):
        assert directory.is_absolute() and directory == root
        raise BoundaryReached()

    monkeypatch.setattr(acceptance, "sealed", seal)
    with pytest.raises(BoundaryReached):
        acceptance.accept(
            run=root.relative_to(ROOT),
            run_pin="0" * 64,
            evaluation=root.relative_to(ROOT),
            evaluation_pin="0" * 64,
            checks="unused",
            checks_pin="0" * 64,
            review="unused",
            review_pin="0" * 64,
            out=output_path(),
        )


def test_relative_checks_input_reaches_pin_as_absolute(monkeypatch):
    path = output_path() / "checks.json"

    def pin(value, expected, **kwargs):
        assert Path(value).is_absolute() and value == path
        raise BoundaryReached()

    monkeypatch.setattr(checks, "pinned", pin)
    with pytest.raises(BoundaryReached):
        checks.verify_checks(path.relative_to(ROOT), "0" * 64)
