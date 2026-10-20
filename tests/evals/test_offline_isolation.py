import builtins
import io
import json
import socket
import subprocess
import sys
from pathlib import Path

from conftest import BASE, refresh

from evals.intelligence_v1.validate import validate_dataset


def test_ISOLATION01_runtime_reads_only_controlled_bundle_and_never_writes(bundle, monkeypatch):
    path = refresh(bundle)
    opened = []
    original_builtin, original_io = builtins.open, io.open

    def guard(original):
        def open_file(file, mode="r", *args, **kwargs):
            assert isinstance(file, (str, bytes, Path)), "unexpected descriptor access"
            target = Path(file).resolve()
            assert target.is_relative_to(bundle.resolve()), f"outside bundle: {target.name}"
            assert not set(target.parts) & {".env", ".local", "dev-diaries"}
            assert not any(flag in mode for flag in "wax+"), "validator attempted write"
            opened.append(target.relative_to(bundle).as_posix())
            return original(file, mode, *args, **kwargs)
        return open_file

    def no_network(*args, **kwargs):
        raise AssertionError("network access attempted")

    with monkeypatch.context() as scoped:
        scoped.setattr(builtins, "open", guard(original_builtin))
        scoped.setattr(io, "open", guard(original_io))
        scoped.setattr(socket, "getaddrinfo", no_network)
        scoped.setattr(socket, "create_connection", no_network)
        scoped.setattr(socket.socket, "connect", no_network)
        report = validate_dataset(path)
    assert report.ok and "manifests/dataset_manifest.json" in opened
    # After hash verification, payloads are parsed from the captured bytes, not reopened.
    assert opened.count(BASE + "documents.jsonl") == 1


def test_cli_exit_status_and_no_business_module_imports(bundle):
    path = refresh(bundle)
    script = r'''
import json, os, sys
from pathlib import Path
from evals.intelligence_v1.validate import main
root=Path(sys.argv[1]).resolve()
runtime=[Path(sys.prefix).resolve(),Path(sys.base_prefix).resolve()]
def guard(event,args):
    if event.startswith('socket.'):
        raise AssertionError('network attempted')
    if event=='open':
        file,mode,flags=args
        if isinstance(file,(str,bytes)):
            target=Path(file).resolve()
            dependency_code=(target.suffix in {'.py','.pyc','.pyd'}
                             and any(target.is_relative_to(p) for p in runtime))
            if not target.is_relative_to(root) and not dependency_code:
                raise AssertionError('outside data read')
            if flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
                raise AssertionError('write attempted')
sys.addaudithook(guard)
status=main(['--manifest',str(root/'manifests/dataset_manifest.json'),'--strict'])
assert not any(x.startswith('cfaw_news.') for x in sys.modules)
sys.exit(status)
'''
    result = subprocess.run([sys.executable, "-B", "-c", script, str(bundle)],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["ok"]
    gold = bundle / BASE / "gold.jsonl"
    gold.write_bytes(gold.read_bytes() + b" ")
    bad = subprocess.run([sys.executable, "-B", "-m", "evals.intelligence_v1.validate",
                          "--manifest", str(path), "--strict"],
                         capture_output=True, text=True, timeout=20)
    assert bad.returncode == 1
    assert {x["code"] for x in json.loads(bad.stdout)["errors"]} == {"SHA_MISMATCH"}
    arguments = subprocess.run([sys.executable, "-B", "-m", "evals.intelligence_v1.validate"],
                               capture_output=True, timeout=20)
    assert arguments.returncode == 2
