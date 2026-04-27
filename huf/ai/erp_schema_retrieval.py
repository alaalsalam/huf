import json
import frappe


DEFAULT_BLOCKED_DOCTYPES = [
    "User", "Role", "Has Role", "DocPerm", "Custom DocPerm", "System Settings",
    "OAuth Client", "OAuth Bearer Token", "OAuth Authorization Code", "API Key",
    "Integration Request", "Error Log", "Access Log", "Activity Log", "GL Entry",
    "Salary Slip", "Payroll Entry", "Employee", "Employee Checkin", "Employee Advance",
]

def _json_list(value):
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return [x.strip() for x in str(value).split(",") if x.strip()]


def get_ai_settings():
    defaults = {
        "enable_chat_widget": True,
        "enable_debug": False,
        "debug_roles": ["System Manager", "HUF Administrator"],
        "enable_rag": True,
        "allowed_doctypes": [],
        "blocked_doctypes": list(DEFAULT_BLOCKED_DOCTYPES),
        "enable_redaction": True,
        "redaction_rules": {},
        "require_confirmation_for_sensitive_actions": True,
    }
    try:
        if frappe.db.exists("DocType", "HUF AI Settings"):
            doc = frappe.get_single("HUF AI Settings")
            defaults.update({
                "enable_chat_widget": bool(doc.enable_chat_widget),
                "default_agent": doc.default_agent,
                "default_model_provider": doc.default_model_provider,
                "enable_debug": bool(doc.enable_debug),
                "debug_roles": _json_list(doc.debug_roles),
                "enable_rag": bool(doc.enable_rag),
                "enable_streaming": bool(doc.enable_streaming),
                "max_tokens": doc.max_tokens,
                "temperature": doc.temperature,
                "daily_cost_limit": doc.daily_cost_limit,
                "allowed_doctypes": _json_list(doc.allowed_doctypes),
                "blocked_doctypes": sorted(set(DEFAULT_BLOCKED_DOCTYPES).union(_json_list(doc.blocked_doctypes))),
                "allow_full_erp_access_roles": _json_list(doc.allow_full_erp_access_roles),
                "enable_redaction": bool(doc.enable_redaction),
                "redaction_rules": doc.redaction_rules,
                "require_confirmation_for_sensitive_actions": bool(doc.require_confirmation_for_sensitive_actions),
            })
    except Exception:
        frappe.log_error("Unable to read HUF AI Settings", "HUF AI Settings")
    return defaults


def _allowed_by_settings(doctype, settings):
    allowed = set(settings.get("allowed_doctypes") or [])
    blocked = set(settings.get("blocked_doctypes") or [])
    if allowed and doctype not in allowed:
        return False
    if doctype in blocked:
        return False
    return True


def build_schema_index():
    settings = get_ai_settings()
    rows = frappe.get_list("DocType", fields=["name", "module", "custom"], limit_page_length=5000, order_by="name asc")
    index = []
    for row in rows:
        doctype = row.name
        if not _allowed_by_settings(doctype, settings):
            continue
        if not frappe.has_permission(doctype, "read", user=frappe.session.user):
            continue
        try:
            meta = frappe.get_meta(doctype)
        except Exception:
            continue
        fields = []
        searchable = [doctype, meta.module or row.module or ""]
        for df in meta.fields:
            if df.fieldtype in ("Section Break", "Column Break", "Tab Break", "HTML", "Button"):
                continue
            if df.fieldtype in ("Password", "Signature") or df.hidden or df.fieldname in {"api_key", "api_secret", "access_token", "refresh_token", "password", "private_key", "secret"}:
                continue
            fields.append({"fieldname": df.fieldname, "label": df.label, "fieldtype": df.fieldtype, "options": df.options})
            searchable.extend([df.fieldname or "", df.label or "", df.fieldtype or "", df.options or ""])
        index.append({
            "doctype": doctype,
            "module": meta.module or row.module,
            "custom": bool(row.custom),
            "title_field": meta.title_field,
            "fields": fields,
            "search_text": " ".join(str(x).lower() for x in searchable if x),
        })
    return index


def search_schema(query, limit=10):
    query = (query or "").lower().strip()
    if not query:
        return []
    terms = [t for t in query.replace("_", " ").split() if len(t) > 1]
    scored = []
    for item in build_schema_index():
        text = item["search_text"]
        score = sum(3 if t == item["doctype"].lower() else 1 for t in terms if t in text)
        if score:
            public = dict(item)
            public.pop("search_text", None)
            public["score"] = score
            scored.append(public)
    scored.sort(key=lambda x: (-x["score"], x["doctype"]))
    return scored[: int(limit or 10)]
