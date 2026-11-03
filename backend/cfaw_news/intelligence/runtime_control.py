"""One request deadline/cancellation scope, including nested Pydantic recomputation."""

import time
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

from .contracts import LedgerError

_CURRENT = ContextVar("g4_runtime_control", default=None)


class Control:
    """Cooperative stage checks, without resetting the request deadline in validators."""
    def __init__(self, *, cancelled=lambda: False, timeout_seconds=30, clock=time.monotonic):
        if timeout_seconds <= 0 or timeout_seconds > 60:
            raise LedgerError("G4_RUNTIME_INVALID_TIMEOUT")
        self.cancelled, self.clock = cancelled, clock
        self.deadline = clock() + timeout_seconds
        self.log = []

    def check(self, stage):
        if self.cancelled():
            raise LedgerError("G4_RUNTIME_CANCELLED")
        if self.clock() >= self.deadline:
            raise LedgerError("G4_RUNTIME_TIMEOUT")
        self.log.append(stage)


def current():
    value = _CURRENT.get()
    if value is None:
        raise LedgerError("G4_RUNTIME_CONTROL_REQUIRED")
    return value


@contextmanager
def control_scope(control=None):
    inherited = _CURRENT.get()
    if control is not None and (not isinstance(control, Control)
                                or inherited is not None and inherited is not control):
        raise LedgerError("G4_RUNTIME_CONTROL_MISMATCH")
    value = inherited or control or Control()
    token = _CURRENT.set(value)
    try:
        yield value
    finally:
        _CURRENT.reset(token)


def model_control(info):
    context = info.context if isinstance(info.context, dict) else {}
    return control_scope(context.get("control"))


def controlled(function):
    @wraps(function)
    def wrapped(*args, control=None, **kwargs):
        with control_scope(control) as active:
            active.check(function.__name__)
            value = function(*args, **kwargs)
            active.check(function.__name__ + "_complete")
            return value
    return wrapped
