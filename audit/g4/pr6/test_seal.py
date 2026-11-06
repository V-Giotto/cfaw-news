"""Regression for Windows aliasing and fail-closed recursive QA verification."""

import json

import pytest

from audit.g4.pr6 import seal


def test_business_manifest_preserved_and_included(tmp_path, monkeypatch):
    monkeypatch.setattr(seal, "ROOT", tmp_path)
    folder = tmp_path / ".tmp/output"
    folder.mkdir(parents=True)
    business = folder / "manifest.json"
    original = b'{"revision":"native-business-output","value":42}\n'
    business.write_bytes(original)
    roots = seal.build_roots([folder])
    assert business.read_bytes() == original
    assert not business.samefile(folder / seal.INDEX)
    index = json.loads((folder / seal.INDEX).read_text())
    assert index["files"]["manifest.json"] == seal.pin(business)
    assert seal.verify_roots(roots)["business_manifests"] == 1
    with pytest.raises(FileExistsError):
        seal.build_roots([folder])
    assert business.read_bytes() == original


def test_case_insensitive_collision_rejected_before_any_write(tmp_path, monkeypatch):
    monkeypatch.setattr(seal, "ROOT", tmp_path)
    folder = tmp_path / ".tmp/output"
    (folder / "child").mkdir(parents=True)
    occupied = folder / "child" / seal.INDEX.upper()
    occupied.write_bytes(b"do not overwrite")
    with pytest.raises(FileExistsError):
        seal.build_roots([folder])
    assert occupied.read_bytes() == b"do not overwrite"
    assert not (folder / seal.INDEX).exists()
    with pytest.raises(FileExistsError):
        seal.write_new(occupied.with_name(occupied.name.lower()), {})


def test_parallel_tree_has_exact_counts_and_checks_all_business_manifests(tmp_path, monkeypatch):
    monkeypatch.setattr(seal, "ROOT", tmp_path)
    folder = tmp_path / ".tmp/output"
    for i in range(32):
        leaf = folder / str(i)
        leaf.mkdir(parents=True)
        (leaf / "manifest.json").write_bytes(str(i).encode())
        (leaf / "input.json").write_bytes(b"input")
    roots = seal.build_roots([folder])
    result = seal.verify_roots(roots)
    assert (result["directories"], result["files"], result["business_manifests"]) == (33, 64, 32)
    (folder / "31/manifest.json").write_bytes(b"corrupt")
    with pytest.raises(ValueError):
        seal.verify_roots(roots)


@pytest.mark.parametrize("change", ["file", "index", "extra", "missing"])
def test_recursive_corruption_refused(tmp_path, monkeypatch, change):
    monkeypatch.setattr(seal, "ROOT", tmp_path)
    folder = tmp_path / ".tmp/output"
    leaf = folder / "leaf"
    leaf.mkdir(parents=True)
    (leaf / "manifest.json").write_bytes(b"original")
    roots = seal.build_roots([folder])
    assert seal.verify_roots(roots)["files"] == 1
    if change == "file":
        (leaf / "manifest.json").write_bytes(b"corrupt")
    elif change == "index":
        (leaf / seal.INDEX).write_bytes(b"corrupt")
    elif change == "extra":
        (leaf / "extra").write_bytes(b"unsealed")
    else:
        (leaf / "manifest.json").unlink()
    with pytest.raises(ValueError):
        seal.verify_roots(roots)
