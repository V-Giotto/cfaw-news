"""Verify the native dependency tree before runtime models/computation import it."""

import hashlib
import importlib.util
import json
from pathlib import Path

from .contracts import LedgerError
from .native_lock import CORE_RETRIEVAL_PIN, PINS

ENGINE_PIN = hashlib.sha256(json.dumps(dict(native=PINS, core_retrieval=CORE_RETRIEVAL_PIN),
    sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def verify():
    spec = importlib.util.find_spec("evals")
    if spec is None or not spec.submodule_search_locations:
        raise LedgerError("G4_NATIVE_DEPENDENCY_REQUIRED")
    root = Path(next(iter(spec.submodule_search_locations))).resolve()
    for relative, pin in PINS.items():
        path = root / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != pin:
            raise LedgerError("G4_NATIVE_DEPENDENCY_MISMATCH")
    core = importlib.util.find_spec("cfaw_news.retrieval")
    if core is None or hashlib.sha256(Path(core.origin).read_bytes()).hexdigest() != CORE_RETRIEVAL_PIN:
        raise LedgerError("G4_NATIVE_DEPENDENCY_MISMATCH")
    return root
