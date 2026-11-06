"""Exclusive QA indexes, distinct from every business manifest; verify every reference."""

import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from audit.g4.pr6.freeze import ROOT, sha

INDEX = ".cfaw-g4-pr6-qa-index-v2.json"
REVISION = "g4-pr6-directory-index-v2"


def pin(path):
    return {"sha256": sha(path), "bytes": path.stat().st_size}


def write_new(path, value):
    """Never overwrite, including a differently cased file on Windows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if any(p.name.casefold() == path.name.casefold() for p in path.parent.iterdir()):
        raise FileExistsError(str(path))
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def linked(path):
    return path.is_symlink() or path.is_junction()


def preflight(folder):
    if linked(folder):
        raise ValueError("linked root")
    names = set()
    for path in folder.iterdir():
        if path.name.casefold() in names:
            raise ValueError("case-colliding directory entries")
        names.add(path.name.casefold())
        if path.name.casefold() == INDEX.casefold():
            raise FileExistsError(str(path))
        if path.is_dir() and not linked(path) and path.name != "__pycache__":
            preflight(path)


def _build(folder, executor=None):
    files, children, excluded = {}, {}, []
    for path in sorted(folder.iterdir()):
        if linked(path) or path.name == "__pycache__":
            excluded.append(path.name)
        elif path.is_dir():
            children[path.name] = executor.submit(_build, path) if executor else _build(path)
        elif path.is_file():
            files[path.name] = pin(path)
    if executor:
        children = {name: future.result() for name, future in children.items()}
    target = folder / INDEX
    write_new(target, dict(revision=REVISION, directory=folder.relative_to(ROOT).as_posix(),
                           files=files, children=children, excluded=excluded,
                           self_hash="Only this QA index is excluded; business manifests are ordinary files"))
    return pin(target)


def build_roots(roots):
    # Reject a collision anywhere before writing any index in any root.
    for folder in roots:
        assert folder.resolve().is_relative_to(ROOT / ".tmp"), folder
        preflight(folder)
    with ThreadPoolExecutor(max_workers=8) as executor:
        return {folder.relative_to(ROOT).as_posix(): _build(folder, executor) for folder in roots}


def _name(value):
    if not value or value in (".", "..") or "/" in value or "\\" in value or Path(value).is_absolute():
        raise ValueError("unsafe index reference")
    return value


def verify_roots(roots):
    total = Counter()

    def verify(folder, expected, executor=None):
        counts = Counter(directories=0, files=0, business_manifests=0, bytes=0)
        index = folder / INDEX
        if pin(index) != expected or linked(index):
            raise ValueError("index hash mismatch: " + str(index))
        data = json.loads(index.read_text(encoding="utf-8"))
        if data["revision"] != REVISION or data["directory"] != folder.relative_to(ROOT).as_posix():
            raise ValueError("index identity mismatch")
        actual = {p.name for p in folder.iterdir() if p.name.casefold() != INDEX.casefold()}
        declared = list(data["files"]) + list(data["children"]) + data["excluded"]
        if len({n.casefold() for n in declared}) != len(declared) or actual != set(declared):
            raise ValueError("directory inventory mismatch: " + str(folder))
        counts["directories"] += 1
        for name, expected_file in data["files"].items():
            path = folder / _name(name)
            if linked(path) or not path.is_file() or pin(path) != expected_file:
                raise ValueError("file hash mismatch: " + str(path))
            counts["files"] += 1
            counts["bytes"] += expected_file["bytes"]
            counts["business_manifests"] += name.casefold() == "manifest.json"
        pending = []
        for name, expected_child in data["children"].items():
            path = folder / _name(name)
            if linked(path) or not path.is_dir():
                raise ValueError("linked or missing child")
            if executor:
                pending.append(executor.submit(verify, path, expected_child))
            else:
                counts.update(verify(path, expected_child))
        for name in data["excluded"]:
            path = folder / _name(name)
            if name != "__pycache__" and not linked(path):
                raise ValueError("unapproved exclusion")

        for future in pending:
            counts.update(future.result())
        return counts

    with ThreadPoolExecutor(max_workers=8) as executor:
        for name, expected in roots.items():
            folder = ROOT / name
            assert folder.resolve().is_relative_to(ROOT / ".tmp")
            total.update(verify(folder, expected, executor))
    return dict(status="PASS_RECURSIVE_ALL_REFERENCES", **total)
