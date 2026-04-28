import json
import frappe
from frappe.utils import add_to_date, now_datetime, get_datetime

SENSITIVE_ACTION_WORDS = {
    "delete", "remove", "trash", "submit", "cancel", "email", "send_email",
    "payment", "pay", "salary", "journal", "ledger", "role", "permission", "user",
    "create", "update", "set_value", "write", "send email", "mail", "submit document", "cancel document",
    "حذف", "احذف", "إحذف", "امسح", "مسح", "ازل", "أزل", "حط في السلة",
    "اعتمد", "اعتماد", "رحل", "ترحيل", "قدم", "تقديم",
    "إلغاء", "الغاء", "الغِ", "الغ", "إلغ",
    "دفع", "سداد", "صرف", "راتب", "رواتب",
    "أرسل", "ارسل", "إرسال", "ارسال", "بريد", "ايميل",
    "انشئ", "أنشئ", "اضف", "أضف", "عدل", "تعديل", "غير", "غيّر",
}
SENSITIVE_ARABIC_DOCTYPE_WORDS = {
    "فاتورة مبيعات", "فواتير مبيعات", "فاتورة مشتريات", "فواتير مشتريات",
    "قيد يومية", "قيود يومية", "سند دفع", "سند قبض", "دفعة", "دفعات",
    "مستخدم", "مستخدمين", "دور", "أدوار", "صلاحية", "صلاحيات",
    "راتب", "رواتب", "موظف", "موظفين", "حساب", "حسابات",
}
SENSITIVE_DOCTYPES = {
    "Payment Entry", "Salary Slip", "Employee", "User", "Role", "Has Role",
    "DocPerm", "Custom DocPerm", "GL Entry", "Journal Entry", "Sales Invoice",
    "Purchase Invoice", "Purchase Order", "Sales Order", "Payroll Entry",
    "Account", "Company", "Bank Account", "Email Queue", "System Settings",
    "OAuth Client", "OAuth Bearer Token", "OAuth Authorization Code", "API Key",
    "Integration Request", "DocPerm", "Custom DocPerm",
}

READ_ONLY_ARABIC_HINTS = {
    "اعطني", "أعطني", "اعرض", "وريني", "وين", "لماذا", "ليش", "ما ",
    "من ", "لخص", "ملخص", "تقرير", "قائمة", "القائمة", "اهم", "أهم",
}
COMPLAINT_HINTS = {
    "لقد ارسل لي", "لقد أرسل لي", "ارسلت لي", "أرسلت لي", "ارسل لي عميل",
    "أرسل لي عميل", "وين قائمه", "وين قائمة", "وين القائمة", "عميل واحد",
}
EXPLICIT_SEND_HINTS = {
    "ارسل بريد", "أرسل بريد", "إرسال بريد", "ارسال بريد",
    "ارسل ايميل", "أرسل ايميل", "أرسل إيميل", "send email", "email customer",
}
EXPLICIT_CREATE_HINTS = {
    "انشئ", "أنشئ", "اضف", "أضف", "create", "add",
}


def _settings_enabled():
    try:
        if frappe.db.exists("DocType", "HUF AI Settings"):
            value = frappe.get_single("HUF AI Settings").require_confirmation_for_sensitive_actions
            return True if value in (None, "") else bool(value)
    except Exception:
        pass
    return True


def classify_action_sensitivity(action, doctype=None):
    action_text = (action or "").lower()
    if doctype in SENSITIVE_DOCTYPES:
        return "high"
    if any(hint in action_text for hint in COMPLAINT_HINTS):
        return "normal"
    if any(hint in action_text for hint in EXPLICIT_SEND_HINTS):
        return "high"
    if any(hint in action_text for hint in EXPLICIT_CREATE_HINTS):
        return "high"
    if any(hint in action_text for hint in READ_ONLY_ARABIC_HINTS):
        if not any(word in action_text for word in {"احذف", "حذف", "اعتمد", "الغ", "إلغاء", "الغاء", "عدل", "تعديل", "دفع", "سداد"}):
            return "normal"
    if any(word in action_text for word in SENSITIVE_ACTION_WORDS):
        return "high"
    if any(word in action_text for word in SENSITIVE_ARABIC_DOCTYPE_WORDS) and any(word in action_text for word in {"آخر", "اخر", "كل", "جميع"}):
        return "high"
    return "normal"


def requires_confirmation(action, doctype=None, payload=None):
    if not _settings_enabled():
        return False
    return classify_action_sensitivity(action, doctype) == "high"


def _safe_payload(payload):
    from huf.ai.redaction import redact_sensitive_data
    try:
        redacted = redact_sensitive_data(payload, {"enable_redaction": True})
        return json.loads(redacted) if isinstance(redacted, str) and redacted.startswith(("{", "[")) else {"summary": redacted}
    except Exception:
        return {"summary": "[payload redacted]"}


def create_pending_confirmation(action, doctype=None, document_name=None, payload=None, session=None, message=None, summary=None):
    doc = frappe.get_doc({
        "doctype": "HUF AI Pending Confirmation",
        "user": frappe.session.user,
        "session": session,
        "message": message,
        "action": action,
        "doctype_name": doctype,
        "document_name": document_name,
        "payload": json.dumps(_safe_payload(payload or {}), ensure_ascii=False, default=str),
        "summary": summary or f"تأكيد تنفيذ {action} على {doctype or 'النظام'}",
        "status": "Pending",
        "expires_on": add_to_date(now_datetime(), hours=2),
    })
    doc.insert(ignore_permissions=True)
    return {
        "id": doc.name,
        "action": action,
        "doctype": doctype,
        "document_name": document_name,
        "summary": doc.summary,
        "expires_on": doc.expires_on,
    }


def confirm_pending_action(confirm_action_id):
    if not confirm_action_id:
        frappe.throw("Confirmation id is required")
    doc = frappe.get_doc("HUF AI Pending Confirmation", confirm_action_id)
    if doc.user != frappe.session.user and "System Manager" not in frappe.get_roles(frappe.session.user):
        frappe.throw("Not permitted to confirm this action", frappe.PermissionError)
    if doc.status != "Pending":
        frappe.throw("Confirmation is not pending")
    if doc.expires_on and get_datetime(doc.expires_on) < now_datetime():
        doc.status = "Expired"
        doc.save(ignore_permissions=True)
        frappe.throw("Confirmation has expired")
    if doc.doctype_name and doc.document_name and not frappe.has_permission(doc.doctype_name, "write", doc=doc.document_name, user=frappe.session.user):
        frappe.throw("You no longer have permission to execute this action", frappe.PermissionError)
    doc.status = "Confirmed"
    doc.confirmed_on = now_datetime()
    doc.save(ignore_permissions=True)
    payload = {}
    if doc.payload:
        try:
            payload = json.loads(doc.payload)
        except Exception:
            payload = {}
    return {"confirmation": doc.name, "action": doc.action, "payload": payload, "doctype": doc.doctype_name, "document_name": doc.document_name}
