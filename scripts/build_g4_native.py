"""Build a minimal companion wheel containing unchanged native Python dependencies.

No root pyproject/control-plane mutation, datasets, labels, fixtures or user material.
"""

import argparse
import base64
import csv
import hashlib
import io
import json
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def wheel(files, distribution, version, directory, requires=()):
    name = f"{distribution}-{version}"
    info = name + ".dist-info"
    files = dict(files)
    files[info + "/METADATA"] = (f"Metadata-Version: 2.1\nName: {distribution.replace('_', '-')}\n"
        f"Version: {version}\nRequires-Python: >=3.11\n"
        "Summary: Controlled CFAW G4 runtime build profile\n"
        + "".join(f"Requires-Dist: {r}\n" for r in requires)).encode()
    files[info + "/WHEEL"] = b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
    records = io.StringIO(newline="")
    writer = csv.writer(records, lineterminator="\n")
    for path, payload in sorted(files.items()):
        pin = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b"=").decode()
        writer.writerow((path, "sha256=" + pin, len(payload)))
    writer.writerow((info + "/RECORD", "", ""))
    files[info + "/RECORD"] = records.getvalue().encode()
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (name + "-py3-none-any.whl")
    with target.open("xb") as stream, zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as wheel:
        for path, payload in sorted(files.items()):
            entry = zipfile.ZipInfo(path, date_time=(2026, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            wheel.writestr(entry, payload)
    return target


def build(directory):
    from cfaw_news.intelligence.native import ENGINE_PIN, verify
    from cfaw_news.intelligence.native_lock import PINS
    base = verify()
    return wheel({"evals/" + p: (base / p).read_bytes() for p in sorted(PINS)},
                 "cfaw_news_g4_native", "0.1.0+" + ENGINE_PIN[:12], directory)


def build_core(directory):
    from cfaw_news.intelligence.native import ENGINE_PIN
    source = ROOT / "backend"
    files = {p.relative_to(source).as_posix(): p.read_bytes()
             for p in (source / "cfaw_news").rglob("*.py")}
    files.update({p.relative_to(source).as_posix(): p.read_bytes()
                  for p in (source / "cfaw_news/prompts").glob("*.txt")})
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    return wheel(files, "cfaw_news", project["version"] + "+g4pr3", directory,
                 [*project["dependencies"], "cfaw-news-g4-native==0.1.0+" + ENGINE_PIN[:12]])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--core", action="store_true", help="Also build the unchanged-backend runtime profile")
    args = parser.parse_args()
    targets = [build(args.out)]
    if args.core:
        targets.append(build_core(args.out))
    print(json.dumps([dict(path=str(t), sha256=hashlib.sha256(t.read_bytes()).hexdigest()) for t in targets]))


if __name__ == "__main__":
    main()
