import json
import re
import time
from typing import Any, Dict, List

import frappe
from frappe import _


TOOL_TYPE = "ERP Deep Analytics"
TOOL_NAME = "trilogy_erp_database_analyst"
PROMPT_MARKER = "TRILOGY_ERP_ANALYTICS_ENGINE_V2"
OPENAI_MODEL = "gpt-5-mini"
FRIENDLY_ADVANCED_DISABLED = (
    "التحليل المتقدم غير مفعّل لهذه المحادثة. يمكنني المحاولة بطريقة أبسط، "
    "مثل تحديد الفترة أو المستودع أو نوع المستند المطلوب."
)

CORE_DOCTYPES = [
    "Customer", "Supplier", "Item", "Lead", "Opportunity",
    "Sales Order", "Sales Order Item", "Sales Invoice", "Sales Invoice Item",
    "Purchase Order", "Purchase Order Item", "Purchase Invoice", "Purchase Invoice Item",
    "Payment Entry", "Journal Entry", "Journal Entry Account", "GL Entry",
    "Account", "Company", "Cost Center", "Mode of Payment",
    "Material Request", "Material Request Item", "Stock Entry", "Stock Entry Detail",
    "Project", "Task", "Employee",
]

SUBMITTED_DOCTYPES = {
    "Sales Order", "Sales Invoice", "Purchase Order", "Purchase Invoice",
    "Payment Entry", "Journal Entry", "Material Request", "Stock Entry",
}

BLOCKED_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|replace|create|grant|revoke|rename|call|load|outfile|infile)\b",
    re.IGNORECASE,
)


def _compact(value: Any, max_chars: int = 12000) -> Any:
    text = json.dumps(value, ensure_ascii=False, default=str)
    if len(text) <= max_chars:
        return value
    return {"truncated": True, "preview": text[:max_chars], "original_chars": len(text)}


def _get_openai_key() -> str:
    if not frappe.db.exists("AI Provider", "OpenAI"):
        frappe.throw(_("OpenAI provider is not configured."))
    provider = frappe.get_doc("AI Provider", "OpenAI")
    api_key = provider.get_password("api_key")
    if not api_key:
        frappe.throw(_("OpenAI API key is not configured."))
    return api_key


def _openai_text(prompt: str, system: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=_get_openai_key())
    response = client.responses.create(
        model=frappe.conf.get("trilogy_ai_analytics_model") or OPENAI_MODEL,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )

    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text.strip()

    data = response.model_dump() if hasattr(response, "model_dump") else {}
    chunks = []
    for item in data.get("output", []) or []:
        for content in item.get("content", []) or []:
            if content.get("text"):
                chunks.append(content["text"])
    return "\n".join(chunks).strip()


def _json_from_text(text: str) -> Dict[str, Any]:
    cleaned = (text or "").strip()
    cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(cleaned)
    except Exception:
        match = re.search(r"\{.*\}", cleaned, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def _field_allowed(df) -> bool:
    return df.fieldtype not in {
        "Section Break", "Column Break", "Tab Break", "HTML", "Button",
        "Image", "Attach Image", "Signature", "Fold", "Heading",
    }


def _schema_context() -> str:
    blocks = []
    system_fields = [
        ("name", "Data", "Document ID"),
        ("docstatus", "Int", "Document Status"),
        ("creation", "Datetime", "Created On"),
        ("modified", "Datetime", "Modified On"),
        ("owner", "Link", "Owner"),
    ]

    for doctype in CORE_DOCTYPES:
        if not frappe.db.exists("DocType", doctype):
            continue
        meta = frappe.get_meta(doctype)
        fields = list(system_fields)
        for df in meta.fields:
            if _field_allowed(df) and df.fieldname:
                label = df.label or df.fieldname
                extra = f" -> {df.options}" if df.options and df.fieldtype in {"Link", "Table", "Select"} else ""
                fields.append((df.fieldname, df.fieldtype, f"{label}{extra}"))
        field_text = ", ".join(f"{name}:{ftype}:{label}" for name, ftype, label in fields[:55])
        docstatus_note = "transaction: use docstatus = 1 when asking posted/submitted records" if doctype in SUBMITTED_DOCTYPES else "master/reference: do not filter by docstatus unless the user asks"
        blocks.append(f"`tab{doctype}` ({doctype}) [{docstatus_note}] fields: {field_text}")

    return "\n".join(blocks)


def _extract_tables(sql: str) -> List[str]:
    return sorted(set(re.findall(r"`(tab[^`]+)`", sql or "")))


def _doctype_from_table(table: str) -> str:
    return table[3:] if table.startswith("tab") else table


def _validate_sql(sql: str) -> Dict[str, Any]:
    sql = (sql or "").strip().rstrip(";")
    if not sql:
        return {"ok": False, "error": "Empty SQL"}

    lowered = sql.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        return {"ok": False, "error": "Only SELECT queries are allowed"}
    if BLOCKED_SQL.search(sql):
        return {"ok": False, "error": "Blocked SQL keyword detected"}
    if ";" in sql:
        return {"ok": False, "error": "Multiple SQL statements are not allowed"}

    tables = _extract_tables(sql)
    for table in tables:
        doctype = _doctype_from_table(table)
        if not frappe.db.exists("DocType", doctype):
            return {"ok": False, "error": f"Unknown table: {table}"}
        if not frappe.has_permission(doctype, "read"):
            return {"ok": False, "error": f"No read permission for {doctype}"}

    return {"ok": True, "tables": tables, "sql": sql}


def _add_limit(sql: str) -> str:
    if re.search(r"\blimit\s+\d+\b", sql, flags=re.I):
        return sql
    if re.search(r"\b(count|sum|avg|min|max)\s*\(", sql, flags=re.I):
        return sql
    return f"{sql} LIMIT 50"


def _generate_sql(question: str) -> Dict[str, Any]:
    system = (
        "You are a senior ERPNext data analyst. Generate safe read-only MariaDB SQL only. "
        "Use only the provided schema. Always return JSON with keys: sql, rationale. "
        "Never generate INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CALL, CREATE, or multiple statements."
    )
    prompt = f"""
Question:
{question}

Schema:
{_schema_context()}

Rules:
- Use exact backticked table names like `tabSales Invoice`.
- Use exact field names.
- Use docstatus = 1 only for transaction doctypes such as invoices, orders, payments, journal entries, stock entries, and material requests.
- Do not add docstatus filters to master/reference doctypes such as Customer, Supplier, Item, Account, Company, Employee, Project, or Task unless the user explicitly asks.
- For unpaid receivables use outstanding_amount when available.
- Keep results concise and add LIMIT for list queries.
- Return JSON only.
"""
    return _json_from_text(_openai_text(prompt, system))


def _format_answer(question: str, sql: str, rows: List[Dict[str, Any]]) -> str:
    system = (
        "You are TrilogyAi, an Arabic executive ERP assistant. "
        "Answer briefly, clearly, and practically. Do not mention demo data. "
        "Use the provided SQL result only; do not invent numbers."
    )
    prompt = f"""
السؤال: {question}
SQL: {sql}
النتيجة JSON:
{json.dumps(rows[:20], ensure_ascii=False, default=str)}

اكتب إجابة عربية قصيرة. إذا كانت النتيجة رقمًا واحدًا، اذكره مباشرة. إذا كانت قائمة، لخّص أهم ما يظهر.
"""
    return _openai_text(prompt, system)


@frappe.whitelist(allow_guest=False)
def analyze_erp_question(question: str, chat_id: str | None = None, request_id: str | None = None) -> Dict[str, Any]:
    """Run native read-only ERP analytics inside HUF without external analytics apps."""
    if frappe.session.user == "Guest":
        frappe.throw(_("Please log in to use TrilogyAi ERP analytics."))

    try:
        from huf.ai.erp_schema_retrieval import get_ai_settings
        settings = get_ai_settings()
        if not (settings.get("enable_advanced_erp_query") and settings.get("chat_execution_mode") == "Advanced ERP Query"):
            return {
                "ok": False,
                "engine": "TrilogyAi ERP Analytics",
                "question": question,
                "answer": FRIENDLY_ADVANCED_DISABLED,
                "result": [],
                "validation": {"ok": False, "advanced_query_disabled": True},
                "error": "Advanced ERP Query is disabled",
            }
    except Exception:
        frappe.log_error("Unable to read HUF AI Settings for TrilogyAi analytics", "TrilogyAi ERP Analytics")
        return {
            "ok": False,
            "engine": "TrilogyAi ERP Analytics",
            "question": question,
            "answer": FRIENDLY_ADVANCED_DISABLED,
            "result": [],
            "validation": {"ok": False, "advanced_query_disabled": True},
            "error": "Advanced ERP Query is disabled",
        }

    question = (question or "").strip()
    if not question:
        frappe.throw(_("Question is required."))

    start = time.time()
    try:
        generated = _generate_sql(question)
        sql = _add_limit((generated.get("sql") or "").strip().rstrip(";"))
        validation = _validate_sql(sql)
        if not validation.get("ok"):
            return {
                "ok": False,
                "engine": "TrilogyAi ERP Analytics",
                "question": question,
                "answer": "تعذر تنفيذ التحليل لأن الاستعلام غير آمن أو غير صالح.",
                "sql": sql,
                "tables": validation.get("tables") or _extract_tables(sql),
                "result": [],
                "validation": validation,
                "error": validation.get("error"),
                "elapsed_seconds": round(time.time() - start, 2),
            }

        rows = frappe.db.sql(validation["sql"], as_dict=True)
        answer = _format_answer(question, validation["sql"], rows)
        return {
            "ok": True,
            "engine": "TrilogyAi ERP Analytics",
            "question": question,
            "formatted_question": question,
            "answer": answer,
            "sql": validation["sql"],
            "tables": validation.get("tables"),
            "fields": None,
            "result": _compact(rows),
            "validation": validation,
            "error": None,
            "elapsed_seconds": round(time.time() - start, 2),
        }
    except Exception as exc:
        frappe.log_error(frappe.get_traceback(), "TrilogyAi ERP Analytics Error")
        return {
            "ok": False,
            "engine": "TrilogyAi ERP Analytics",
            "question": question,
            "answer": "",
            "error": str(exc),
            "elapsed_seconds": round(time.time() - start, 2),
        }


@frappe.whitelist(allow_guest=False)
def setup_trilogy_erp_analytics() -> Dict[str, Any]:
    """Create the HUF-native ERP analytics tool and attach it to chat agents."""
    if frappe.session.user != "Administrator" and not frappe.has_permission("Agent Tool Function", "write"):
        frappe.throw(_("You do not have permission to configure TrilogyAi analytics."))

    if not frappe.db.exists("Agent Tool Type", TOOL_TYPE):
        frappe.get_doc({"doctype": "Agent Tool Type", "name1": TOOL_TYPE}).insert(ignore_permissions=True)

    params = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "Arabic or English ERP analytics question to answer from live ERPNext data.",
            }
        },
        "required": ["question"],
        "additionalProperties": False,
    }

    if frappe.db.exists("Agent Tool Function", TOOL_NAME):
        tool = frappe.get_doc("Agent Tool Function", TOOL_NAME)
    else:
        tool = frappe.get_doc({"doctype": "Agent Tool Function", "tool_name": TOOL_NAME})

    tool.update({
        "description": (
            "Native TrilogyAi read-only ERP analytics engine. Use for financial, sales, inventory, "
            "customer, supplier, and operational questions that require live ERPNext database analysis."
        ),
        "tool_type": TOOL_TYPE,
        "types": "Custom Function",
        "function_path": "huf.ai.trilogy_erp_analytics.analyze_erp_question",
        "is_read_only": 1,
        "allowed_for_guest": 0,
        "required_permission": "read",
        "params": json.dumps(params, ensure_ascii=False, indent=2),
    })
    tool.parameters = []
    tool.append("parameters", {
        "fieldname": "question",
        "label": "Question",
        "type": "string",
        "description": "ERP analytics question to answer from live data.",
        "required": 1,
    })

    if tool.is_new():
        tool.insert(ignore_permissions=True)
    else:
        tool.save(ignore_permissions=True)

    prompt_block = f"""

[{PROMPT_MARKER}]
عند طلب المستخدم تحليلاً رقمياً أو تقريراً يعتمد على بيانات ERPNext الحية، استخدم الأداة `{TOOL_NAME}` أولاً.
اعرض الناتج بشكل مختصر وواضح:
1. النتيجة المباشرة.
2. جدول صغير عند وجود أرقام متعددة.
3. أهم إجراءين مقترحين.
لا تعرض SQL للمستخدم إلا إذا طلب التفاصيل التقنية.
إذا رجعت الأداة خطأ، اذكر السبب العملي واقترح سؤالاً أبسط أو نطاقاً زمنياً أوضح.
"""

    linked = []
    updated_prompts = []
    agents = frappe.get_all(
        "Agent",
        filters={"allow_chat": 1, "disabled": 0},
        fields=["name"],
        limit_page_length=100,
    )

    for row in agents:
        agent = frappe.get_doc("Agent", row.name)
        existing_tools = {d.tool for d in (agent.get("agent_tool") or []) if d.tool}
        if TOOL_NAME not in existing_tools:
            agent.append("agent_tool", {"tool": TOOL_NAME})
            linked.append(agent.name)

        current = agent.get("instructions") or ""
        if PROMPT_MARKER in current:
            current = current.split(f"[{PROMPT_MARKER}]")[0].rstrip()
        if "TRILOGY_CHANGAI_ANALYTICS_BRIDGE_V1" in current:
            current = current.split("[TRILOGY_CHANGAI_ANALYTICS_BRIDGE_V1]")[0].rstrip()
        agent.instructions = current.rstrip() + prompt_block
        updated_prompts.append(agent.name)
        agent.save(ignore_permissions=True)

    frappe.db.commit()
    return {"tool": TOOL_NAME, "tool_type": TOOL_TYPE, "linked_agents": linked, "updated_prompts": updated_prompts}


@frappe.whitelist(allow_guest=False)
def healthcheck() -> Dict[str, Any]:
    """Small backend verification for the native HUF ERP analytics engine."""
    return analyze_erp_question("What is the total number of customers?")

