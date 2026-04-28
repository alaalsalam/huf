import json
from collections import defaultdict
from datetime import timedelta
import re

import frappe
from frappe.utils import flt, getdate, nowdate

from huf.ai.erp_schema_retrieval import get_ai_settings


TOOL_TYPE = "HUF Safe ERP"
HOME_AGENT = "HUF Home Assistant"
FRIENDLY_ERROR = "لم أتمكن من جلب هذه البيانات الآن بسبب الصلاحيات أو قيود النظام. يمكنك تحديد فترة أو مستودع لتضييق النطاق."
PERMISSION_ERROR = "لا أملك صلاحية كافية لعرض هذه البيانات حسب صلاحيات حسابك."

SAFE_TOOL_NAMES = [
    "huf_sales_summary",
    "huf_overdue_invoices",
    "huf_stock_summary",
    "huf_low_stock_items",
    "huf_top_customers",
    "huf_create_followup_task_request",
]


def _settings():
    return get_ai_settings()


def _enabled():
    return bool(_settings().get("enable_safe_erp_tools", True))


def _record_limit(limit=None):
    configured = int(_settings().get("safe_tool_record_limit") or 500)
    requested = int(limit or configured)
    return max(1, min(requested, configured, 1000))


def _max_scan_records():
    configured = int(_settings().get("safe_tool_max_scan_records") or 5000)
    return max(500, min(configured, 20000))


def _display_limit(limit=None):
    configured = int(_settings().get("safe_tool_display_limit") or 20)
    requested = int(limit or configured)
    return max(1, min(requested, configured, 100))


def _month_range(from_date=None, to_date=None):
    if from_date and to_date:
        return str(getdate(from_date)), str(getdate(to_date))
    current = getdate(nowdate())
    start = current.replace(day=1)
    end = current
    return str(start), str(end)


def _current_year_range():
    current = getdate(nowdate())
    return str(current.replace(month=1, day=1)), str(current)


def _last_12_months_range():
    current = getdate(nowdate())
    return str(current - timedelta(days=365)), str(current)


def _parse_period(period=None, from_date=None, to_date=None):
    if from_date and to_date:
        return str(getdate(from_date)), str(getdate(to_date)), "explicit"
    text = str(period or "").strip().lower()
    current = getdate(nowdate())
    year_match = re.search(r"(20\d{2})", text)
    if year_match:
        year = int(year_match.group(1))
        start = current.replace(year=year, month=1, day=1)
        if any(term in text for term in ["كامل", "كاملة", "full", "entire"]):
            end = current.replace(year=year, month=12, day=31)
        elif year == current.year:
            end = current
        else:
            end = current.replace(year=year, month=12, day=31)
        return str(start), str(end), f"year:{year}"
    if any(term in text for term in ["السنة الحالية", "هذا العام", "هذه السنة", "current year"]):
        start, end = _current_year_range()
        return start, end, "current_year"
    if any(term in text for term in ["آخر سنة", "اخر سنة", "last year", "last 12"]):
        start, end = _last_12_months_range()
        return start, end, "last_12_months"
    if any(term in text for term in ["هذا الشهر", "الشهر الحالي", "current month"]):
        start, end = _month_range()
        return start, end, "current_month"
    start, end = _month_range()
    return start, end, "default_current_month"


def _paged_get_list(doctype, filters, fields, order_by=None, max_records=None):
    max_records = max_records or _max_scan_records()
    page_size = min(500, max_records)
    rows = []
    start = 0
    while len(rows) < max_records:
        batch = frappe.get_list(
            doctype,
            filters=filters,
            fields=fields,
            order_by=order_by,
            limit_start=start,
            limit_page_length=min(page_size, max_records - len(rows)),
        )
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < page_size:
            break
        start += len(batch)
    return rows, len(rows) >= max_records


def _safe_fields(doctype, fields):
    meta = frappe.get_meta(doctype)
    allowed = {"name", "owner", "creation", "modified", "docstatus"}
    allowed.update(df.fieldname for df in meta.fields if not df.hidden and df.fieldtype not in ("Password", "Signature"))
    blocked = {"api_key", "api_secret", "access_token", "refresh_token", "password", "private_key", "secret"}
    return [field for field in fields if field in allowed and field not in blocked]


def _can_read(doctype):
    return frappe.has_permission(doctype, "read", user=frappe.session.user)


def _friendly_failure(exc, title="HUF Safe ERP Tool"):
    frappe.log_error(frappe.get_traceback(), title)
    return {
        "success": False,
        "answer": FRIENDLY_ERROR,
        "error_hidden": True,
    }


def _disabled_response():
    return {
        "success": False,
        "answer": FRIENDLY_ERROR,
        "error_hidden": True,
        "disabled": True,
    }


def _permission_response(doctype):
    return {
        "success": False,
        "answer": PERMISSION_ERROR,
        "permission_denied": True,
        "doctype": doctype,
    }


@frappe.whitelist()
def huf_sales_summary(from_date=None, to_date=None, customer=None, limit=None):
    """Summarize submitted Sales Invoices using permission-aware Frappe reads only."""
    if not _enabled():
        return _disabled_response()
    if not _can_read("Sales Invoice"):
        return _permission_response("Sales Invoice")
    try:
        from_date, to_date = _month_range(from_date, to_date)
        filters = {
            "docstatus": 1,
            "posting_date": ["between", [from_date, to_date]],
        }
        if customer:
            filters["customer"] = customer
        fields = _safe_fields("Sales Invoice", ["name", "customer", "posting_date", "grand_total", "outstanding_amount", "status", "currency"])
        rows = frappe.get_list(
            "Sales Invoice",
            filters=filters,
            fields=fields,
            order_by="posting_date desc, modified desc",
            limit_page_length=_record_limit(limit),
        )
        total = sum(flt(row.get("grand_total")) for row in rows)
        outstanding = sum(flt(row.get("outstanding_amount")) for row in rows)
        display = rows[:_display_limit(limit)]
        return {
            "success": True,
            "answer": "تم جلب ملخص المبيعات من فواتير المبيعات المعتمدة ضمن الفترة المحددة.",
            "period": {"from_date": from_date, "to_date": to_date},
            "summary": {
                "invoice_count": len(rows),
                "grand_total": total,
                "outstanding_amount": outstanding,
                "currencies": sorted({row.get("currency") for row in rows if row.get("currency")}),
            },
            "columns": fields,
            "rows": display,
            "capped": len(rows) >= _record_limit(limit),
        }
    except Exception as exc:
        return _friendly_failure(exc, "HUF Safe ERP Sales Summary")


@frappe.whitelist()
def huf_overdue_invoices(customer=None, limit=20):
    """List overdue submitted Sales Invoices with outstanding amounts."""
    if not _enabled():
        return _disabled_response()
    if not _can_read("Sales Invoice"):
        return _permission_response("Sales Invoice")
    try:
        filters = {
            "docstatus": 1,
            "outstanding_amount": [">", 0],
            "due_date": ["<", nowdate()],
        }
        if customer:
            filters["customer"] = customer
        fields = _safe_fields("Sales Invoice", ["name", "customer", "due_date", "outstanding_amount", "currency", "status"])
        rows = frappe.get_list(
            "Sales Invoice",
            filters=filters,
            fields=fields,
            order_by="due_date asc, outstanding_amount desc",
            limit_page_length=_display_limit(limit),
        )
        total = sum(flt(row.get("outstanding_amount")) for row in rows)
        return {
            "success": True,
            "answer": "هذه الفواتير المتأخرة حسب صلاحيات حسابك.",
            "summary": {"invoice_count": len(rows), "outstanding_amount": total},
            "columns": fields,
            "rows": rows,
        }
    except Exception as exc:
        return _friendly_failure(exc, "HUF Safe ERP Overdue Invoices")


@frappe.whitelist()
def huf_stock_summary(warehouse=None, limit=None):
    """Summarize stock bins without raw SQL."""
    if not _enabled():
        return _disabled_response()
    if not _can_read("Bin"):
        return _permission_response("Bin")
    try:
        filters = {}
        if warehouse:
            filters["warehouse"] = warehouse
        fields = _safe_fields("Bin", ["item_code", "warehouse", "actual_qty", "projected_qty", "stock_value"])
        source_limit = _record_limit(limit)
        rows = frappe.get_list(
            "Bin",
            filters=filters,
            fields=fields,
            order_by="stock_value desc, actual_qty asc",
            limit_page_length=source_limit,
        )
        actual_qty = sum(flt(row.get("actual_qty")) for row in rows)
        projected_qty = sum(flt(row.get("projected_qty")) for row in rows)
        stock_value = sum(flt(row.get("stock_value")) for row in rows)
        by_warehouse = defaultdict(lambda: {"actual_qty": 0.0, "projected_qty": 0.0, "stock_value": 0.0, "rows": 0})
        for row in rows:
            key = row.get("warehouse") or "غير محدد"
            by_warehouse[key]["actual_qty"] += flt(row.get("actual_qty"))
            by_warehouse[key]["projected_qty"] += flt(row.get("projected_qty"))
            by_warehouse[key]["stock_value"] += flt(row.get("stock_value"))
            by_warehouse[key]["rows"] += 1
        warehouse_rows = [
            {"warehouse": key, **value}
            for key, value in sorted(by_warehouse.items(), key=lambda item: item[1]["stock_value"], reverse=True)
        ][: _display_limit(limit)]
        needs_filter = not warehouse and len(rows) >= source_limit
        return {
            "success": True,
            "answer": "هذا ملخص المخزون حسب السجلات المتاحة لصلاحياتك." if not needs_filter else "تم عرض ملخص محدود. هل تريد الملخص لكل المستودعات أم لمستودع محدد؟",
            "summary": {
                "bin_count": len(rows),
                "actual_qty": actual_qty,
                "projected_qty": projected_qty,
                "stock_value": stock_value,
            },
            "columns": ["warehouse", "actual_qty", "projected_qty", "stock_value", "rows"],
            "rows": warehouse_rows,
            "needs_clarification": needs_filter,
        }
    except Exception as exc:
        return _friendly_failure(exc, "HUF Safe ERP Stock Summary")


@frappe.whitelist()
def huf_low_stock_items(warehouse=None, limit=20):
    """Return items with non-positive actual or projected quantity from Bin."""
    if not _enabled():
        return _disabled_response()
    if not _can_read("Bin"):
        return _permission_response("Bin")
    try:
        filters = {}
        if warehouse:
            filters["warehouse"] = warehouse
        fields = _safe_fields("Bin", ["item_code", "warehouse", "actual_qty", "projected_qty"])
        rows = frappe.get_list(
            "Bin",
            filters=filters,
            fields=fields,
            order_by="actual_qty asc, projected_qty asc",
            limit_page_length=_record_limit(),
        )
        low_rows = [
            row for row in rows
            if flt(row.get("actual_qty")) <= 0 or flt(row.get("projected_qty")) <= 0
        ][: _display_limit(limit)]
        return {
            "success": True,
            "answer": "تم اعتبار الصنف منخفضًا عندما تكون الكمية الفعلية أو المتوقعة صفرًا أو أقل، بدون افتراض مستويات إعادة طلب غير موجودة.",
            "method": "actual_qty <= 0 OR projected_qty <= 0",
            "columns": fields,
            "rows": low_rows,
        }
    except Exception as exc:
        return _friendly_failure(exc, "HUF Safe ERP Low Stock Items")


@frappe.whitelist()
def huf_top_customers(from_date=None, to_date=None, period=None, limit=10):
    """Rank customers by submitted Sales Invoice grand total in the selected period."""
    if not _enabled():
        return _disabled_response()
    if not _can_read("Sales Invoice"):
        return _permission_response("Sales Invoice")
    try:
        from_date, to_date, period_source = _parse_period(period, from_date, to_date)
        requested_limit = _display_limit(limit or 10)
        fields = _safe_fields("Sales Invoice", ["customer", "grand_total", "outstanding_amount", "currency", "posting_date"])
        rows, capped = _paged_get_list(
            "Sales Invoice",
            filters={"docstatus": 1, "posting_date": ["between", [from_date, to_date]]},
            fields=fields,
            order_by="posting_date desc",
            max_records=_max_scan_records(),
        )
        totals = defaultdict(lambda: {"customer": "", "grand_total": 0.0, "outstanding_amount": 0.0, "invoice_count": 0})
        currencies = set()
        for row in rows:
            customer = row.get("customer") or "غير محدد"
            totals[customer]["customer"] = customer
            totals[customer]["grand_total"] += flt(row.get("grand_total"))
            totals[customer]["outstanding_amount"] += flt(row.get("outstanding_amount"))
            totals[customer]["invoice_count"] += 1
            if row.get("currency"):
                currencies.add(row.get("currency"))
        ranked = sorted(totals.values(), key=lambda row: row["grand_total"], reverse=True)[:requested_limit]
        if len(ranked) == 1:
            answer = "وجدت عميلاً واحدًا فقط ضمن الفترة والصلاحيات الحالية."
        elif ranked:
            answer = f"تم عرض {len(ranked)} عملاء من أصل {len(totals)} عميل ضمن الفترة والصلاحيات الحالية."
        else:
            answer = "لم أجد عملاء لديهم مبيعات معتمدة ضمن الفترة والصلاحيات الحالية."
        if capped:
            answer += " النتائج مبنية على عدد السجلات الممسوحة فقط وقد لا تشمل كل البيانات."
        return {
            "success": True,
            "answer": answer,
            "period": {"from_date": from_date, "to_date": to_date, "source": period_source},
            "summary": {
                "customers_found": len(totals),
                "customers_returned": len(ranked),
                "requested_limit": requested_limit,
                "records_scanned": len(rows),
                "scan_capped": capped,
                "currencies": sorted(currencies),
            },
            "columns": ["customer", "grand_total", "outstanding_amount", "invoice_count"],
            "rows": ranked,
        }
    except Exception as exc:
        return _friendly_failure(exc, "HUF Safe ERP Top Customers")


@frappe.whitelist()
def huf_create_followup_task_request(customer=None, subject=None, due_date=None, description=None):
    """Prepare a follow-up task request; actual creation requires explicit confirmation."""
    return {
        "success": True,
        "requires_confirmation": True,
        "answer": "يمكنني تجهيز مهمة متابعة، لكن لن يتم إنشاء أي سجل قبل تأكيدك الصريح.",
        "confirmation": {
            "action": "create_followup_task",
            "doctype": "ToDo",
            "summary": {
                "customer": customer,
                "subject": subject or "متابعة عميل",
                "due_date": due_date,
                "description": description,
            },
        },
    }


SAFE_TOOL_DEFINITIONS = [
    {
        "tool_name": "huf_sales_summary",
        "description": "Read-only Arabic ERP tool. Summarizes submitted Sales Invoices for a date range using frappe.get_list only. Use for: اعرض مبيعات هذا الشهر.",
        "function_path": "huf.ai.safe_erp_tools.huf_sales_summary",
        "parameters": [
            {"name": "from_date", "type": "string", "description": "Optional start date."},
            {"name": "to_date", "type": "string", "description": "Optional end date."},
            {"name": "customer", "type": "string", "description": "Optional customer filter."},
            {"name": "limit", "type": "integer", "description": "Optional safe source/display limit."},
        ],
    },
    {
        "tool_name": "huf_overdue_invoices",
        "description": "Read-only Arabic ERP tool. Lists overdue submitted Sales Invoices with outstanding amounts using frappe.get_list only. Use for: ما الفواتير المتأخرة؟",
        "function_path": "huf.ai.safe_erp_tools.huf_overdue_invoices",
        "parameters": [
            {"name": "customer", "type": "string", "description": "Optional customer filter."},
            {"name": "limit", "type": "integer", "description": "Display limit."},
        ],
    },
    {
        "tool_name": "huf_stock_summary",
        "description": "Read-only Arabic ERP tool. Summarizes Bin stock quantities and value by warehouse using frappe.get_list only. Use for: لخص حالة المخزون.",
        "function_path": "huf.ai.safe_erp_tools.huf_stock_summary",
        "parameters": [
            {"name": "warehouse", "type": "string", "description": "Optional warehouse filter."},
            {"name": "limit", "type": "integer", "description": "Optional safe source/display limit."},
        ],
    },
    {
        "tool_name": "huf_low_stock_items",
        "description": "Read-only Arabic ERP tool. Finds items with actual or projected quantity at or below zero using Bin and frappe.get_list only. Use for: ما الأصناف منخفضة الكمية؟",
        "function_path": "huf.ai.safe_erp_tools.huf_low_stock_items",
        "parameters": [
            {"name": "warehouse", "type": "string", "description": "Optional warehouse filter."},
            {"name": "limit", "type": "integer", "description": "Display limit."},
        ],
    },
    {
        "tool_name": "huf_top_customers",
        "description": "Read-only Arabic ERP tool. Ranks customers by submitted Sales Invoice totals in a date range using frappe.get_list only. Use for: من هم أفضل العملاء هذا الشهر؟",
        "function_path": "huf.ai.safe_erp_tools.huf_top_customers",
        "parameters": [
            {"name": "from_date", "type": "string", "description": "Optional start date."},
            {"name": "to_date", "type": "string", "description": "Optional end date."},
            {"name": "period", "type": "string", "description": "Optional Arabic or English period, e.g. خلال سنة 2026, هذا الشهر, آخر سنة."},
            {"name": "limit", "type": "integer", "description": "Display limit, default 10."},
        ],
    },
    {
        "tool_name": "huf_create_followup_task_request",
        "description": "Safe confirmation-only tool. Prepares a customer follow-up task request and requires explicit confirmation before any write.",
        "function_path": "huf.ai.safe_erp_tools.huf_create_followup_task_request",
        "parameters": [
            {"name": "customer", "type": "string", "description": "Customer to follow up."},
            {"name": "subject", "type": "string", "description": "Task subject."},
            {"name": "due_date", "type": "string", "description": "Optional due date."},
            {"name": "description", "type": "string", "description": "Optional task details."},
        ],
    },
]


HOME_ASSISTANT_INSTRUCTIONS = """
أنت مساعد HUF الذكي داخل ERPNext باسم Trilogy Ai.

قواعد الإجابة:
- إذا كان السؤال بالعربية فأجب بالعربية، وإذا كان بالإنجليزية فأجب بالإنجليزية.
- ابدأ بالنتيجة مباشرة، ثم جدول صغير عند وجود أرقام أو سجلات.
- لا تخترع أرقامًا أو سجلات. استخدم الأدوات الآمنة المتاحة فقط.
- لا تستخدم SQL خام ولا تذكر SQL أو أسماء الأدوات الداخلية للمستخدم.
- إذا لم تتوفر صلاحية أو بيانات، قل ذلك بوضوح وباختصار.
- إذا كان السؤال واسعًا جدًا، اسأل سؤالًا توضيحيًا واحدًا فقط.
- للعمليات الحساسة مثل الحذف، الاعتماد، الإلغاء، الإرسال، الفواتير، المدفوعات، المستخدمين، الصلاحيات، الرواتب، والقيود المالية: اطلب تأكيدًا صريحًا ولا تنفذ مباشرة.

متى تستخدم الأدوات:
- "اعرض مبيعات هذا الشهر" أو أسئلة المبيعات: استخدم huf_sales_summary.
- "ما الفواتير المتأخرة؟": استخدم huf_overdue_invoices.
- "لخص حالة المخزون": استخدم huf_stock_summary.
- "ما الأصناف منخفضة الكمية؟": استخدم huf_low_stock_items.
- "من هم أفضل العملاء هذا الشهر؟": استخدم huf_top_customers.
- "أنشئ مهمة متابعة للعميل": استخدم أداة طلب المتابعة فقط، ولا تنشئ شيئًا بدون تأكيد.

صيغة الرد المفضلة:
1. نتيجة مختصرة.
2. جدول واضح عند توفر بيانات.
3. إجراءان أو ثلاثة كحد أقصى.
4. ثلاثة اقتراحات متابعة جاهزة.
"""


def _ensure_tool_type():
    if not frappe.db.exists("Agent Tool Type", TOOL_TYPE):
        frappe.get_doc({"doctype": "Agent Tool Type", "name1": TOOL_TYPE}).insert(ignore_permissions=True)


def _upsert_tool(definition):
    docname = frappe.db.get_value("Agent Tool Function", {"tool_name": definition["tool_name"]})
    payload = {
        "tool_name": definition["tool_name"],
        "tool_type": TOOL_TYPE,
        "description": definition["description"],
        "types": "Custom Function",
        "function_path": definition["function_path"],
        "required_permission": "read",
        "is_read_only": 1,
        "allowed_for_guest": 0,
        "pass_parameters_as_json": 1,
    }
    if docname:
        doc = frappe.get_doc("Agent Tool Function", docname)
        doc.update(payload)
        doc.set("parameters", [])
    else:
        doc = frappe.get_doc({"doctype": "Agent Tool Function", **payload})
    for param in definition["parameters"]:
        doc.append("parameters", {
            "label": (param.get("label") or param["name"]).replace("_", " ").title(),
            "fieldname": param["name"],
            "type": param["type"],
            "required": int(param.get("required", 0)),
            "description": param.get("description"),
        })
    doc.save(ignore_permissions=True) if docname else doc.insert(ignore_permissions=True)
    return doc.name


def _pick_provider_model():
    provider = frappe.db.exists("AI Provider", "OpenAI") or frappe.db.get_value("AI Provider", {}, "name")
    model = frappe.db.exists("AI Model", "gpt-5-mini") or frappe.db.get_value("AI Model", {"provider": provider}, "name")
    if not provider or not model:
        frappe.throw("HUF Home Assistant requires at least one AI Provider and AI Model.")
    return provider, model


def _ensure_home_agent(tool_names):
    provider, model = _pick_provider_model()
    docname = frappe.db.exists("Agent", HOME_AGENT) or frappe.db.get_value("Agent", {"agent_name": HOME_AGENT}, "name")
    payload = {
        "agent_name": HOME_AGENT,
        "provider": provider,
        "model": model,
        "temperature": 0.2,
        "top_p": 1,
        "disabled": 0,
        "allow_chat": 1,
        "allow_guest": 0,
        "persist_conversation": 1,
        "prompt_mode": "Local",
        "instructions": HOME_ASSISTANT_INSTRUCTIONS,
        "description": "مساعد ERPNext آمن للصفحة الرئيسية يستخدم أدوات قراءة HUF الآمنة فقط.",
        "history_limit": 5,
        "max_turns": 6,
        "max_knowledge_tokens": 1800,
        "show_tool_execution_details": 0,
    }
    if docname:
        doc = frappe.get_doc("Agent", docname)
        doc.update(payload)
        doc.set("agent_tool", [])
    else:
        doc = frappe.get_doc({"doctype": "Agent", **payload})
    for tool_name in tool_names:
        doc.append("agent_tool", {"tool": tool_name})
    doc.save(ignore_permissions=True) if docname else doc.insert(ignore_permissions=True)
    return doc.name


def _update_settings(agent_name):
    if not frappe.db.exists("DocType", "HUF AI Settings"):
        return
    settings = frappe.get_single("HUF AI Settings")
    if hasattr(settings, "enable_safe_erp_tools"):
        settings.enable_safe_erp_tools = 1
    if hasattr(settings, "safe_tool_record_limit") and not settings.safe_tool_record_limit:
        settings.safe_tool_record_limit = 500
    if hasattr(settings, "safe_tool_display_limit") and not settings.safe_tool_display_limit:
        settings.safe_tool_display_limit = 20
    if hasattr(settings, "safe_tool_max_scan_records") and not settings.safe_tool_max_scan_records:
        settings.safe_tool_max_scan_records = 5000
    if hasattr(settings, "chat_execution_mode") and not settings.chat_execution_mode:
        settings.chat_execution_mode = "Native Agent"
    if hasattr(settings, "enable_advanced_erp_query"):
        settings.enable_advanced_erp_query = 0
    if hasattr(settings, "require_confirmation_for_sensitive_actions"):
        settings.require_confirmation_for_sensitive_actions = 1
    if hasattr(settings, "default_home_agent"):
        settings.default_home_agent = agent_name
    settings.save(ignore_permissions=True)


def setup_safe_erp_tools():
    """Idempotently register the safe ERP tool pack and select the HUF home agent."""
    _ensure_tool_type()
    tool_names = [_upsert_tool(definition) for definition in SAFE_TOOL_DEFINITIONS]
    agent_name = _ensure_home_agent(tool_names)
    _update_settings(agent_name)
    frappe.db.commit()
    return {"agent": agent_name, "tools": tool_names}
