"""PR2 pinned dry-run data preparation only; no rankers, predictions or metrics.

All-step output is for the administrator. Give a human reviewer only their current
single-step packet, following ANNOTATION_GUIDE.md; exporting is not distribution.
"""

import argparse
import re
from pathlib import Path

from .contracts import Manifest
from .exceptions import ContractError, DatasetValidationError
from .hashing import canonical_json, sha256_bytes
from .pilot import annotation_packet
from .provenance import SENSITIVE, controlled_path
from .validate import RECORD_MODELS, validate_dataset


def _manifest_location(value):
    path = Path(value).absolute()
    if (path.name != "dataset_manifest.json" or path.parent.name != "manifests"
            or any(p.casefold() in SENSITIVE or p.casefold().startswith(".env")
                   for p in path.parts)):
        raise ContractError("MANIFEST_PATH_INVALID")
    root = path.parent.parent.resolve()
    return root, controlled_path(root, "manifests/dataset_manifest.json")


def _read_input(root, entry):
    raw = controlled_path(root, entry.path).read_bytes()
    if sha256_bytes(raw) != entry.sha256:
        raise ContractError("SHA_MISMATCH", field=entry.path)
    return raw  # Parse the same verified bytes, never reopen them for parsing.


def _output_location(value, bundle_root):
    path = Path(value).absolute().resolve()
    if (path.is_relative_to(bundle_root)
            or any(p.casefold() in {".git", "dev-diaries"}
                   or p.casefold().startswith(".env") or p.endswith((".", " "))
                   or p.casefold().endswith((".db", ".db-wal", ".db-shm")) for p in path.parts)):
        raise ContractError("OUTPUT_PATH_INVALID")
    if path.exists() or path.is_symlink():
        raise ContractError("OUTPUT_EXISTS")
    return path


def export_pilot(manifest_path, *, manifest_sha256, timeline_id, out, step_id=None):
    """Validate a pinned bundle, prepare bytes in memory, then write a NEW directory."""
    pin = manifest_sha256.lower()
    if re.fullmatch(r"[0-9a-f]{64}", pin) is None:
        raise ContractError("MANIFEST_SHA_MISMATCH")
    root, path = _manifest_location(manifest_path)
    raw_manifest = path.read_bytes()
    if sha256_bytes(raw_manifest) != pin:
        raise ContractError("MANIFEST_SHA_MISMATCH")
    report = validate_dataset(path)
    if report.manifest_sha256 != pin:
        raise ContractError("MANIFEST_SHA_MISMATCH")
    manifest = Manifest.model_validate_json(raw_manifest)
    rows = {role: [] for role in ("documents", "personas", "coverage", "steps")}
    template = None
    for entry in manifest.file_hashes:
        if entry.role in rows:
            raw = _read_input(root, entry)
            rows[entry.role].extend(RECORD_MODELS[entry.role].model_validate_json(line)
                                    for line in raw.splitlines())
        elif entry.path == "DEV-01/annotation_template.json" and entry.role == "support":
            template = _read_input(root, entry)
    if template is None:
        raise ContractError("UNLISTED_INPUT", field="annotation_template")
    if timeline_id != "DEV-01":
        raise ContractError("REFERENCE_NOT_FOUND", field="timeline_id")
    steps = sorted((s for s in rows["steps"] if s.timeline_id == timeline_id
                    and (step_id is None or s.step_id == step_id)), key=lambda s: (s.as_of, s.step_id))
    if not steps:
        raise ContractError("REFERENCE_NOT_FOUND", field="step_id")
    output = _output_location(out, root)
    payloads, visibility, hashes = {}, [], []
    for step in steps:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", step.step_id) is None:
            raise ContractError("OUTPUT_PATH_INVALID", field="step_id")
        packet = annotation_packet(rows["documents"], rows["personas"], rows["coverage"], step=step)
        payloads[f"packets/{step.step_id}/packet.json"] = packet
        payloads[f"packets/{step.step_id}/blank_form.json"] = template
        visibility.append({"step_id": step.step_id, "as_of": step.model_dump(mode="json")["as_of"],
                           "persona_version_id": step.persona_version_id,
                           "visible_doc_version_ids": list(step.visible_doc_version_ids)})
        hashes.append({"step_id": step.step_id, "packet_sha256": sha256_bytes(packet)})
    metadata = {"mode": "pr2_dry_run", "timeline_id": timeline_id,
                "manifest_sha256": pin, "dataset_revision": manifest.dataset_revision,
                "packets": hashes, "distribution": "not_distributed",
                "human_annotation": "not_confirmed", "semantic_support": "not_measured"}
    payloads["visible_steps.jsonl"] = "".join(canonical_json(r) + "\n" for r in visibility).encode()
    payloads["run_metadata.json"] = (canonical_json(metadata) + "\n").encode()
    # No output files exist until every input, pin, step and packet has passed.
    output.mkdir(parents=True, exist_ok=False)
    for name, raw in payloads.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)
    return metadata


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path,
                        default=Path(__file__).parent / "manifests/dataset_manifest.json")
    parser.add_argument("--manifest-sha256", required=True, help="Externally pinned Manifest SHA256")
    parser.add_argument("--timeline", choices=["DEV-01"], required=True)
    parser.add_argument("--dry-run", action="store_true", required=True)
    parser.add_argument("--step", help="Export only this step; withhold later packets from annotators")
    parser.add_argument("--out", type=Path, required=True, help="New output directory; never overwritten")
    args = parser.parse_args(argv)
    try:
        metadata = export_pilot(args.manifest, manifest_sha256=args.manifest_sha256,
                                timeline_id=args.timeline, step_id=args.step, out=args.out)
    except DatasetValidationError as error:
        print(canonical_json(error.report.to_dict()))
        return 1
    except ContractError as error:
        print(canonical_json({"ok": False, "errors": [{"code": error.code, "field": error.field}]}))
        return 1
    except (OSError, ValueError, RuntimeError):
        print(canonical_json({"ok": False, "errors": [{"code": "EXPORT_IO_ERROR"}]}))
        return 1
    print(canonical_json({"ok": True, **metadata}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
