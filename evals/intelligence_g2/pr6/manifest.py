"""Explicit roles, source commit binding and exclusive artifact sealing."""

import subprocess
from pathlib import Path

from evals.intelligence_g2.contracts import G1_PIN, PACKAGE, ROOT, json_bytes, read_json
from evals.intelligence_g2.replay import OUTPUT_BASE, output_location, safe_path, write_payloads
from evals.intelligence_v1.hashing import sha256_bytes

from .contracts import CampaignSpec, SourceRelease, fail, parse

FIXTURE = PACKAGE / "fixtures/pr6/v1"
FORBIDDEN = {"reference", "labels", "annotations", "adjudications", "review", "reviews"}


def relative(path):
    p = Path(path)
    if (
        not isinstance(path, str)
        or "\\" in path
        or ":" in path
        or any(x in {"", ".", ".."} for x in path.split("/"))
    ):
        fail("MANIFEST_PATH_INVALID", "path")
    if p.is_absolute() or not p.parts or any(x in {".", ".."} for x in p.parts):
        fail("MANIFEST_PATH_INVALID", "path")
    return p


def pinned(path, pin, *, areas=(PACKAGE, OUTPUT_BASE)):
    path = safe_path(path, areas=areas, code="MANIFEST_PATH_INVALID")
    raw = path.read_bytes()
    if sha256_bytes(raw) != pin:
        fail("SHA_MISMATCH", "artifact")
    return raw


def repo_file(entry):
    return pinned(
        ROOT / relative(entry.path),
        entry.sha256,
        areas=(ROOT / "evals/intelligence_v1", PACKAGE, ROOT / ".tmp"),
    )


def load_campaign(path, pin):
    value = parse(CampaignSpec, read_json(pinned(path, pin)))
    if value.g1_manifest.sha256 != G1_PIN:
        fail("MANIFEST_SHA_MISMATCH", "g1_manifest")
    if value.g1_manifest.path != "evals/intelligence_v1/manifests/dataset_manifest.json":
        fail("PREDICTION_PATH_INVALID", "g1_manifest")
    for name, entry in value.configs.items():
        if entry.path != f"evals/intelligence_g2/manifests/{name}_config.json":
            fail("PREDICTION_PATH_INVALID", "configs")
    for entry, folder in (
        (value.prediction_manifest, "prediction"),
        (value.mock_manifest, "mock-response"),
    ):
        if relative(entry.path).parent != Path("evals/intelligence_g2/fixtures/pr6/v1") / folder:
            fail("PREDICTION_PATH_INVALID", "role_manifest")
    repo_file(value.g1_manifest)
    for entry in value.configs.values():
        repo_file(entry)
    return value


def source_paths():
    paths = set()
    for directory in ("evals", "tests", "backend", "frontend/src"):
        for p in (ROOT / directory).rglob("*"):
            if (
                p.is_file()
                and "__pycache__" not in p.parts
                and not any(x.endswith(".egg-info") for x in p.parts)
                and (p.suffix in {".py", ".json", ".jsonl", ".md", ".txt", ".tsx", ".ts", ".css"})
            ):
                paths.add(p.relative_to(ROOT).as_posix())
    paths.update(
        (
            "AGENTS.md",
            ".gitattributes",
            ".gitignore",
            ".github/workflows/ci.yml",
            "requirements.lock",
            "pyproject.toml",
            "frontend/package-lock.json",
            "frontend/package.json",
            "frontend/vite.config.ts",
            "frontend/tsconfig.json",
            "frontend/index.html",
            "data/archive/articles.json",
            "audit/G0_BASELINE.json",
            "docs/CFAW_News_V1.md",
            "docs/plans/G1_IMPLEMENTATION_PLAN.md",
            "docs/plans/G1_AI_DEVELOPMENT_RULES.md",
            "docs/plans/G2_IMPLEMENTATION_PLAN.md",
            "docs/G2_G3_HANDOFF.md",
        )
    )
    return tuple(sorted(paths))


def fingerprints():
    return {
        p: sha256_bytes(safe_path(ROOT / p, areas=(ROOT,)).read_bytes()) for p in source_paths()
    }


def git(*args):
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, timeout=30)
    if p.returncode:
        fail("G2_PR6_SOURCE_NOT_COMMITTED", "source_commit")
    return p.stdout


def source_release(commit):
    import platform
    from importlib.metadata import version

    import pydantic

    actual = git("rev-parse", "HEAD").decode().strip()
    if commit != actual or len(commit) != 40:
        fail("G2_PR6_SOURCE_NOT_COMMITTED", "source_commit")
    files = fingerprints()
    for path, sha in files.items():
        if sha256_bytes(git("show", commit + ":" + path)) != sha:
            fail("G2_PR6_SOURCE_NOT_COMMITTED", "source_files")
    runtime = {
        p: h
        for p, h in files.items()
        if p.startswith(("evals/", "backend/cfaw_news/retrieval")) and p.endswith(".py")
    }
    import re

    node = subprocess.run(["node", "--version"], capture_output=True, timeout=10)
    node_text = node.stdout.decode("ascii", errors="ignore").strip()
    node_version = (
        node_text
        if node.returncode == 0 and re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", node_text)
        else "unknown"
    )
    return SourceRelease(
        source_commit=commit,
        git_tree=git("rev-parse", commit + "^{tree}").decode().strip(),
        files=files,
        runtime_files=runtime,
        schema_files={p: h for p, h in files.items() if "/schema/" in p},
        dependency_locks={p: files[p] for p in ("requirements.lock", "frontend/package-lock.json")},
        dependency_versions={
            "python": platform.python_version(),
            "pydantic": pydantic.__version__,
            "pytest": version("pytest"),
            "ruff": version("ruff"),
            "node": node_version,
            "platform": __import__("sys").platform,
        },
        reports={p: h for p, h in files.items() if p.startswith("evals/intelligence_g2/reports/")},
    )


def verify_runtime(release):
    required = {
        p.relative_to(ROOT).as_posix()
        for folder in [
            ROOT / "evals/intelligence_v1",
            PACKAGE,
            *[PACKAGE / ("pr" + str(i)) for i in range(2, 7)],
        ]
        for p in folder.glob("*.py")
    }
    required.add("backend/cfaw_news/retrieval.py")
    if not required <= set(release.runtime_files) or any(
        release.files.get(p) != h for p, h in release.runtime_files.items()
    ):
        fail("RUNTIME_CODE_MISMATCH", "runtime_file_set")
    for path, sha in release.runtime_files.items():
        if sha256_bytes((ROOT / relative(path)).read_bytes()) != sha:
            fail("RUNTIME_CODE_MISMATCH", "runtime_source")
    for path, sha in release.dependency_locks.items():
        if sha256_bytes((ROOT / relative(path)).read_bytes()) != sha:
            fail("SHA_MISMATCH", "dependency_locks")


def prediction_catalog(campaign):
    header = read_json(repo_file(campaign.prediction_manifest))
    if header.get("revision") != "g2-pr6-inputs-v1" or header.get("record_origin") != "synthetic":
        fail("G2_PR6_ROLE_INVALID", "prediction_manifest")
    entries = header["files"]
    if len({e["path"] for e in entries}) != len(entries) or any(
        e["role"] not in {"prediction", "prediction_catalog"} for e in entries
    ):
        fail("G2_PR6_ROLE_INVALID", "prediction_files")
    for e in entries:
        if set(relative(e["path"]).parts) & FORBIDDEN:
            fail("PREDICTION_PATH_INVALID", "prediction_files")
    catalogs = [e for e in entries if e["role"] == "prediction_catalog"]
    if len(catalogs) != 1:
        fail("G2_PR6_ROLE_INVALID", "prediction_catalog")
    catalog = catalogs[0]
    root = ROOT / relative(campaign.prediction_manifest.path).parent
    values = read_json(pinned(root / catalog["path"], catalog["sha256"]))["cases"]
    if len({c["case_id"] for c in values}) != len(values) or {c["path"] for c in values} != {
        e["path"] for e in entries if e["role"] == "prediction"
    }:
        fail("G2_PR6_ROLE_INVALID", "prediction_case_set")
    for c in values:
        entry = next(
            (e for e in entries if e["path"] == c["path"] and e["role"] == "prediction"), None
        )
        if entry is None or entry["sha256"] != c["sha256"]:
            fail("G2_PR6_ROLE_INVALID", "prediction_case")
    return root, values


def seal(directory, payloads):
    """Publish a flat stage. Campaign parent paths never change after child creation."""
    write_payloads(output_location(directory), payloads)


def sealed(directory, pin):
    directory = safe_path(directory, areas=(OUTPUT_BASE,))
    if not (directory / "sealed.json").is_file() or not (directory / "run_manifest.json").is_file():
        fail("G2_PR6_UNSEALED", "sealed")
    raw = pinned(directory / "run_manifest.json", pin)
    manifest = read_json(raw)
    marker = read_json(safe_path(directory / "sealed.json", areas=(directory,)).read_bytes())
    if marker != {"run_manifest_sha256": pin, "status": "complete"}:
        fail("G2_PR6_UNSEALED", "sealed")
    if len({e["path"] for e in manifest["artifacts"]}) != len(manifest["artifacts"]):
        fail("DUPLICATE_ID", "artifacts")
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}
    if actual != {e["path"] for e in manifest["artifacts"]} | {"run_manifest.json", "sealed.json"}:
        fail("SHA_MISMATCH", "artifact_set")
    for e in manifest["artifacts"]:
        target = directory / relative(e["path"])
        content = pinned(target, e["sha256"], areas=(directory,))
        if len(content) != e["byte_count"]:
            fail("SHA_MISMATCH", "artifact_size")
    return manifest


def finish(directory, payloads, metadata):
    for name, raw in payloads.items():
        target = directory / relative(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)
    artifacts = [
        dict(
            path=p.relative_to(directory).as_posix(),
            sha256=sha256_bytes(p.read_bytes()),
            byte_count=p.stat().st_size,
        )
        for p in sorted(directory.rglob("*"))
        if p.is_file()
    ]
    manifest = json_bytes({**metadata, "artifacts": artifacts})
    with (directory / "run_manifest.json").open("xb") as stream:
        stream.write(manifest)
    sha = sha256_bytes(manifest)
    with (directory / "sealed.json").open("xb") as stream:
        stream.write(json_bytes(dict(run_manifest_sha256=sha, status="complete")))
    return sha
