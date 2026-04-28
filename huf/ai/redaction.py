import json
import re
import frappe

DEFAULT_PATTERNS = [
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[redacted-email]"),
    (re.compile(r"(?<![\w-])(?!(?:\d{2}[-/]\d{2}[-/]\d{4})(?![\w-]))(?:\+\d{1,3}[\d\s\-()]{7,}\d|0\d[\d\s\-()]{7,}\d)(?![\w-])"), "[redacted-phone]"),
    (re.compile(r"\b\d{12,19}\b"), "[redacted-number]"),
    (re.compile(r"(?i)(api[_-]?key|api[_-]?secret|access[_-]?token|refresh[_-]?token|password|private[_-]?key|secret)\s*[:=]\s*['\"]?[^'\"\s,}]+"), r"\1=[redacted-secret]"),
    (re.compile(r"sk-[A-Za-z0-9_-]{12,}"), "[redacted-openai-key]"),
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{12,}"), "Bearer [redacted-token]"),
]


def _to_text(value):
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return str(value)


def redact_sensitive_data(text_or_payload, settings=None):
    settings = settings or {}
    if not settings.get("enable_redaction", True):
        return text_or_payload
    text = _to_text(text_or_payload)
    for pattern, repl in DEFAULT_PATTERNS:
        text = pattern.sub(repl, text)
    rules = settings.get("redaction_rules") or {}
    if isinstance(rules, str):
        try:
            rules = json.loads(rules)
        except Exception:
            rules = {}
    for raw_pattern, replacement in (rules or {}).items():
        try:
            text = re.sub(raw_pattern, str(replacement), text)
        except Exception:
            frappe.log_error(f"Invalid HUF redaction rule: {raw_pattern}", "HUF AI Redaction")
    return text
