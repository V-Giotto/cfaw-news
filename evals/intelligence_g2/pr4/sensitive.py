"""PR4 publication guard; never redact a quote and present it as original text."""

import re

from evals.intelligence_g2.pr3.extract import SENSITIVE as LEGACY_SENSITIVE
from evals.intelligence_v1.contracts import StrictModel

# Match the quoted key and the first nonblank value character. A closing quote
# immediately after whitespace is an empty example, not a credential value.
# This also conservatively handles a truncated configuration string.
QUOTED_CREDENTIAL = re.compile(
    r'''(?P<key_quote>["'])(?:api[_ -]?key|password|access[_ -]?token|secret)(?P=key_quote)'''
    r'''\s*[:=]\s*(?P<value_quote>["'])\s*(?!(?P=value_quote))\S''', re.I)


def sensitive_text(text):
    return bool(LEGACY_SENSITIVE.search(text) or QUOTED_CREDENTIAL.search(text))


def sensitive_content(value):
    """Inspect actual string values, not escaped JSON serialization of those values."""
    if isinstance(value, StrictModel):
        value = value.model_dump(mode="json")
    if isinstance(value, str):
        return sensitive_text(value)
    if isinstance(value, dict):
        return any(sensitive_content(v) for v in value.values())
    if isinstance(value, (tuple, list)):
        return any(sensitive_content(v) for v in value)
    return False
