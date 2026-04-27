import json
import frappe
from frappe import _
from huf.ai.erp_schema_retrieval import get_ai_settings, search_schema

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


def _json(value, fallback=None):
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return fallback


def _allowed_doctype(doctype, settings):
    allowed = set(settings.get("allowed_doctypes") or [])
    blocked = set(settings.get("blocked_doctypes") or [])
    if allowed and doctype not in allowed:
        return False, _("DocType is not in the allowed AI access list")
    if doctype in blocked:
        return False, _("DocType is blocked for AI access")
    if not frappe.has_permission(doctype, "read", user=frappe.session.user):
        return False, _("You do not have permission to read this DocType")
    return True, None


SENSITIVE_FIELDNAMES = {"password", "api_key", "api_secret", "secret", "access_token", "refresh_token", "private_key", "token", "auth_token"}
SENSITIVE_FIELDTYPES = {"Password", "Signature"}


def _is_safe_field(meta, fieldname):
    if fieldname == "name":
        return True
    df = meta.get_field(fieldname)
    if not df:
        return False
    lowered = (df.fieldname or "").lower()
    if df.hidden or df.fieldtype in SENSITIVE_FIELDTYPES:
        return False
    return not any(sensitive in lowered for sensitive in SENSITIVE_FIELDNAMES)


def _default_fields(doctype):
    meta = frappe.get_meta(doctype)
    fields = ["name"]
    for candidate in [meta.title_field, "posting_date", "transaction_date", "customer", "supplier", "status", "grand_total", "outstanding_amount", "modified"]:
        if candidate and candidate not in fields and _is_safe_field(meta, candidate):
            fields.append(candidate)
    return fields


def _clean_fields(doctype, fields):
    meta = frappe.get_meta(doctype)
    requested = fields or _default_fields(doctype)
    clean = []
    for f in requested:
        if f == "*":
            continue
        if _is_safe_field(meta, f) and f not in clean:
            clean.append(f)
    if "name" not in clean:
        clean.insert(0, "name")
    return clean[:20]


def huf_search_erp_schema(query, limit=10):
    return {"success": True, "results": search_schema(query, limit)}


def huf_safe_get_list(doctype, filters=None, fields=None, limit=20, order_by=None):
    settings = get_ai_settings()
    ok, error = _allowed_doctype(doctype, settings)
    if not ok:
        return {"success": False, "error": str(error), "permission_denied": True, "doctype": doctype}
    filters = _json(filters, {}) or {}
    fields = _clean_fields(doctype, _json(fields, fields) or _default_fields(doctype))
    limit = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))
    data = frappe.get_list(doctype, filters=filters, fields=fields, limit_page_length=limit, order_by=order_by)
    return {"success": True, "doctype": doctype, "fields": fields, "data": data}


def huf_safe_get_doc(doctype, name, fields=None):
    settings = get_ai_settings()
    ok, error = _allowed_doctype(doctype, settings)
    if not ok:
        return {"success": False, "error": str(error), "permission_denied": True, "doctype": doctype}
    if not frappe.has_permission(doctype, "read", doc=name, user=frappe.session.user):
        return {"success": False, "error": _("You do not have permission to read this document"), "permission_denied": True}
    doc = frappe.get_doc(doctype, name)
    values = doc.as_dict()
    wanted = _clean_fields(doctype, _json(fields, fields) or _default_fields(doctype))
    values = {k: values.get(k) for k in wanted}
    return {"success": True, "doctype": doctype, "name": name, "data": values}


def _infer_doctype(user_query):
    hits = search_schema(user_query, limit=5)
    if hits:
        return hits[0]["doctype"], hits
    return None, []


def natural_language_erp_query(user_query, context=None):
    context = context or {}
    doctype = context.get("doctype")
    hits = []
    if not doctype:
        doctype, hits = _infer_doctype(user_query)
    if not doctype:
        return {"success": False, "answer": "لم أجد نوع بيانات مناسب للسؤال. اذكر اسم المستند مثل Sales Invoice أو Customer أو Item.", "suggested_doctypes": []}
    if not hits:
        hits = search_schema(user_query, limit=5)
    fields = _default_fields(doctype)
    result = huf_safe_get_list(doctype, fields=fields, limit=context.get("limit") or 20, order_by="modified desc")
    if not result.get("success"):
        return result
    rows = result.get("data") or []
    return {"success": True, "answer": f"تم العثور على {len(rows)} سجل من {doctype} حسب صلاحياتك.", "doctype": doctype, "schema_matches": hits, "columns": result.get("fields"), "rows": rows}


def huf_natural_language_erp_query(user_query, context=None):
    return natural_language_erp_query(user_query, _json(context, context or {}))
