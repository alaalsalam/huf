import json
import time
import frappe
from frappe import _
from frappe.utils import now_datetime
from huf.ai.agent_integration import run_agent_sync, _is_user_allowed
from huf.ai.conversation_manager import ConversationManager
from huf.ai.erp_schema_retrieval import get_ai_settings, search_schema
from huf.ai.redaction import redact_sensitive_data
from huf.ai.safety import requires_confirmation, create_pending_confirmation, confirm_pending_action


def _require_login():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)


def _json(value, fallback=None):
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return fallback


def _is_admin_or_debug(settings=None):
    settings = settings or get_ai_settings()
    roles = set(settings.get("debug_roles") or ["System Manager", "HUF Administrator"])
    user_roles = set(frappe.get_roles(frappe.session.user))
    return "System Manager" in user_roles or bool(roles.intersection(user_roles))


def _debug_allowed(settings=None):
    settings = settings or get_ai_settings()
    return bool(settings.get("enable_debug")) and _is_admin_or_debug(settings)


def _get_default_agent(settings=None):
    settings = settings or get_ai_settings()
    if settings.get("default_agent") and frappe.db.exists("Agent", settings.get("default_agent")):
        return settings.get("default_agent")
    filters = {}
    try:
        if frappe.get_meta("Agent").has_field("is_active"):
            filters["is_active"] = 1
    except Exception:
        filters = {}
    rows = frappe.get_list("Agent", filters=filters, fields=["name"], order_by="modified desc", limit_page_length=1)
    if not rows and filters:
        rows = frappe.get_list("Agent", fields=["name"], order_by="modified desc", limit_page_length=1)
    if not rows:
        frappe.throw(_("No HUF Agent is configured"))
    return rows[0].name


def _select_agent(agent=None, settings=None):
    agent_name = agent or _get_default_agent(settings)
    if not frappe.db.exists("Agent", agent_name):
        frappe.throw(_("Agent not found"))
    agent_doc = frappe.get_doc("Agent", agent_name)
    if not _is_user_allowed(agent_doc, frappe.session.user):
        frappe.throw(_("You are not authorized to use this agent."), frappe.PermissionError)
    return agent_doc


def _owns_conversation(session_id):
    if not session_id or not frappe.db.exists("Agent Conversation", session_id):
        return False
    if _is_admin_or_debug(get_ai_settings()):
        return True
    owner, external_id = frappe.db.get_value("Agent Conversation", session_id, ["owner", "external_id"])
    return owner == frappe.session.user or external_id == frappe.session.user


def _audit(action, status="Success", session=None, message=None, tool=None, doctype_name=None, document_name=None, input_summary=None, output_summary=None, metadata=None, latency_ms=None):
    try:
        if not frappe.db.exists("DocType", "HUF AI Audit Log"):
            return None
        doc = frappe.get_doc({
            "doctype": "HUF AI Audit Log",
            "user": frappe.session.user,
            "action": action,
            "doctype_name": doctype_name,
            "document_name": document_name,
            "tool": tool,
            "input_summary": (input_summary or "")[:1000],
            "output_summary": (output_summary or "")[:1000],
            "status": status,
            "metadata": json.dumps(metadata or {}, ensure_ascii=False, default=str),
            "timestamp": now_datetime(),
            "session": session,
            "message": message,
            "latency_ms": latency_ms,
        })
        doc.insert(ignore_permissions=True)
        return doc.name
    except Exception:
        frappe.log_error("Unable to write HUF AI audit log", "HUF AI Audit")
        return None


def _latest_assistant_message(conversation):
    rows = frappe.get_list("Agent Message", filters={"conversation": conversation, "role": ["in", ["agent", "assistant"]]}, fields=["name", "content", "creation", "agent_run"], order_by="creation desc", limit_page_length=1)
    return rows[0] if rows else None


def _context(message, doctype=None, docname=None, metadata=None, settings=None):
    settings = settings or get_ai_settings()
    ctx = {
        "current_user": frappe.session.user,
        "roles": frappe.get_roles(frappe.session.user),
        "allowed_doctypes": settings.get("allowed_doctypes"),
        "blocked_doctypes": settings.get("blocked_doctypes"),
        "schema_matches": search_schema(message, limit=6) if settings.get("enable_rag") else [],
        "metadata": metadata or {},
    }
    if doctype and docname:
        if frappe.has_permission(doctype, "read", doc=docname, user=frappe.session.user):
            ctx["current_document"] = {"doctype": doctype, "name": docname}
        else:
            ctx["current_document_error"] = "No read permission for current document"
    return ctx


def _format_prompt(message, ctx, settings=None):
    safe_ctx = redact_sensitive_data(ctx, settings or {"enable_redaction": True})
    safe_message = redact_sensitive_data(message, settings or {"enable_redaction": True})
    return f"""أجب بإيجاز ووضوح وبالعربية إذا كان سؤال المستخدم عربياً. لا تخترع أرقاماً أو سجلات. استخدم أدوات HUF الآمنة عند الحاجة لقراءة ERP.

سياق النظام الآمن:
{safe_ctx[:6000] if isinstance(safe_ctx, str) else json.dumps(safe_ctx, ensure_ascii=False, default=str)[:6000]}

سؤال المستخدم:
{safe_message}
"""


@frappe.whitelist()
def new_session(agent=None, model=None, title=None):
    _require_login()
    agent_doc = _select_agent(agent, get_ai_settings())
    cm = ConversationManager(agent_name=agent_doc.name, channel="Desk Chat", external_id=frappe.session.user)
    conv = cm.create_new_conversation(title=title or "Trilogy Ai Chat")
    if model:
        frappe.db.set_value("Agent Conversation", conv.name, "model", model)
    _audit("new_session", session=conv.name, input_summary=title or "")
    return {"session_id": conv.name, "title": conv.title, "agent": conv.agent, "model": model or conv.model}


@frappe.whitelist()
def get_ui_config():
    _require_login()
    settings = get_ai_settings()
    return {
        "enable_chat_widget": bool(settings.get("enable_chat_widget", True)),
        "debug_available": _debug_allowed(settings),
        "rtl": (frappe.local.lang or "").startswith("ar"),
    }


@frappe.whitelist()
def get_sessions(limit=20):
    _require_login()
    filters = {"channel": ["in", ["Desk Chat", "huf_chat"]]}
    if not _is_admin_or_debug(get_ai_settings()):
        filters["external_id"] = frappe.session.user
    rows = frappe.get_list("Agent Conversation", filters=filters, fields=["name", "title", "agent", "model", "last_activity", "creation", "total_messages"], order_by="last_activity desc, creation desc", limit_page_length=min(max(int(limit or 20), 1), 100))
    return {"sessions": rows, "debug_available": _debug_allowed()}


@frappe.whitelist()
def get_messages(session_id, limit=50):
    _require_login()
    if not _owns_conversation(session_id):
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    rows = frappe.get_list("Agent Message", filters={"conversation": session_id}, fields=["name", "role", "content", "kind", "creation", "agent_run", "user"], order_by="conversation_index asc, creation asc", limit_page_length=min(max(int(limit or 50), 1), 200))
    return {"messages": rows, "debug_available": _debug_allowed()}


@frappe.whitelist()
def delete_session(session_id):
    _require_login()
    if not _owns_conversation(session_id):
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    frappe.db.set_value("Agent Conversation", session_id, "is_active", 0)
    _audit("delete_session", session=session_id)
    return {"success": True}


@frappe.whitelist()
def send_message(message, session_id=None, agent=None, model=None, doctype=None, docname=None, metadata=None, confirm_action_id=None):
    _require_login()
    start = time.time()
    settings = get_ai_settings()
    metadata = _json(metadata, {}) or {}
    if confirm_action_id:
        confirmation = confirm_pending_action(confirm_action_id)
        _audit("confirm_action", session=session_id, metadata=confirmation)
        content = "تم تأكيد الطلب. سيتم تنفيذ الإجراء عبر الأداة الآمنة بعد إعادة فحص الصلاحيات."
        return {"session_id": session_id, "message_id": None, "content": content, "rendered_content": content, "debug_available": _debug_allowed(settings), "requires_confirmation": False, "confirmation": confirmation, "metadata": {"confirmed": True}}
    if not message:
        frappe.throw(_("Message is required"))
    if requires_confirmation(message, doctype=doctype, payload=metadata):
        confirmation = create_pending_confirmation(action=message[:140], doctype=doctype, document_name=docname, payload=metadata, session=session_id, summary="هذا الطلب قد يغير بيانات حساسة ويحتاج موافقة صريحة قبل التنفيذ.")
        _audit("send_message", status="Needs Confirmation", session=session_id, input_summary=message, metadata={"confirmation": confirmation})
        content = "هذا الطلب يتضمن إجراءً حساساً. راجع الملخص ثم اضغط تأكيد إذا كنت تريد التنفيذ."
        return {"session_id": session_id, "message_id": None, "content": content, "rendered_content": content, "debug_available": _debug_allowed(settings), "requires_confirmation": True, "confirmation": confirmation, "metadata": {}}
    agent_doc = _select_agent(agent, settings)
    if session_id and not _owns_conversation(session_id):
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    ctx = _context(message, doctype=doctype, docname=docname, metadata=metadata, settings=settings)
    result = run_agent_sync(agent_name=agent_doc.name, prompt=_format_prompt(message, ctx, settings), provider=agent_doc.provider, model=model or agent_doc.model, channel_id="Desk Chat", external_id=frappe.session.user, conversation_id=session_id)
    conversation_id = result.get("conversation_id") or session_id
    assistant = _latest_assistant_message(conversation_id) if conversation_id else None
    content = result.get("response") or result.get("content") or (assistant.content if assistant else "تم تنفيذ الطلب، لكن لم يتم توليد نص واضح.")
    content = redact_sensitive_data(content, settings)
    latency_ms = int((time.time() - start) * 1000)
    message_id = assistant.name if assistant else None
    run_id = result.get("agent_run_id") or result.get("run_id")
    _audit("send_message", session=conversation_id, message=message_id, input_summary=message, output_summary=content, metadata={"run_id": run_id, "context_summary": redact_sensitive_data(ctx, settings)[:2000]}, latency_ms=latency_ms)
    return {"session_id": conversation_id, "message_id": message_id, "content": content, "rendered_content": content, "debug_available": _debug_allowed(settings), "requires_confirmation": False, "confirmation": None, "metadata": {"run_id": run_id, "agent": agent_doc.name, "model": model or agent_doc.model, "latency_ms": latency_ms}}


@frappe.whitelist()
def get_debug_trace(session_id=None, message_id=None, run_id=None):
    _require_login()
    if not _debug_allowed(get_ai_settings()):
        frappe.throw(_("Debug trace is not available for this user"), frappe.PermissionError)
    filters = {}
    if run_id:
        filters["name"] = run_id
    elif session_id:
        filters["conversation"] = session_id
    runs = frappe.get_list("Agent Run", filters=filters, fields=["name", "agent", "status", "prompt", "response", "model", "provider", "start_time", "end_time", "conversation"], order_by="creation desc", limit_page_length=10)
    tool_calls = frappe.get_list("Agent Tool Call", filters={"agent_run": ["in", [r.name for r in runs]]}, fields=["name", "agent_run", "tool", "status", "tool_args", "tool_result", "error_message", "creation"], order_by="creation asc", limit_page_length=50) if runs else []
    audits = frappe.get_list("HUF AI Audit Log", filters={"session": session_id} if session_id else {}, fields=["name", "action", "status", "tool", "input_summary", "output_summary", "latency_ms", "timestamp"], order_by="creation desc", limit_page_length=20) if frappe.db.exists("DocType", "HUF AI Audit Log") else []
    return {"runs": runs, "tool_calls": tool_calls, "audit": audits, "message_id": message_id}


@frappe.whitelist()
def submit_feedback(message_id, rating, comment=None):
    _require_login()
    if not message_id or not frappe.db.exists("Agent Message", message_id):
        frappe.throw(_("Message not found"))
    msg = frappe.get_doc("Agent Message", message_id)
    if not _owns_conversation(msg.conversation):
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    feedback = "Thumbs Up" if str(rating).lower() in ("positive", "thumbs up", "up", "مفيد") else "Thumbs Down"
    doc = frappe.get_doc({
        "doctype": "Agent Run Feedback",
        "feedback": feedback,
        "comments": comment,
        "agent_message": message_id,
        "agent": msg.agent,
        "provider": msg.provider,
        "model": msg.model,
    })
    doc.insert(ignore_permissions=True)
    _audit("submit_feedback", session=msg.conversation, message=message_id, status="Success", metadata={"rating": rating})
    return {"success": True, "feedback_id": doc.name}
