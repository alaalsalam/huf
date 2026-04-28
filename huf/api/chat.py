import json
import re
import time
import frappe
from frappe import _
from frappe.utils import now_datetime
from huf.ai.agent_integration import run_agent_sync, _is_user_allowed
from huf.ai.conversation_manager import ConversationManager
from huf.ai.erp_schema_retrieval import get_ai_settings, search_schema
from huf.ai.redaction import redact_sensitive_data
from huf.ai.safety import requires_confirmation, create_pending_confirmation, confirm_pending_action


INVENTORY_SUGGESTIONS = [
    "لخص حالة المخزون حسب المستودع",
    "اعرض الأصناف منخفضة الكمية في مستودع محدد",
    "اعرض أعلى 10 أصناف حسب قيمة المخزون",
]
SUGGESTED_PROMPT_GROUPS = [
    {"key": "sales", "label": "المبيعات", "prompts": ["اعرض مبيعات هذا الشهر", "من هم أفضل العملاء هذا الشهر؟", "قارن مبيعات هذا الشهر بالشهر السابق"]},
    {"key": "inventory", "label": "المخزون", "prompts": ["لخص حالة المخزون", "ما الأصناف منخفضة الكمية؟", "اعرض أعلى الأصناف حسب قيمة المخزون"]},
    {"key": "receivables", "label": "المستحقات", "prompts": ["ما الفواتير المتأخرة؟", "اعرض العملاء الأعلى مديونية", "ما الفواتير المستحقة هذا الأسبوع؟"]},
    {"key": "tasks", "label": "المهام", "prompts": ["أنشئ مهمة متابعة للعميل", "لخص المهام المفتوحة", "ما المهام المتأخرة؟"]},
    {"key": "general", "label": "عام", "prompts": ["ماذا أستطيع أن أسأل؟", "ساعدني في تحليل أداء الشركة اليوم"]},
]
SAFE_DEFAULT_AGENT_NAMES = {
    "HUF Home Assistant",
    "HUF Sales Analyst",
    "HUF Stock Analyst",
    "HUF Receivables Assistant",
    "HUF Task Assistant",
}
SMART_MODEL_AGENT_NAMES = {"HUF Home Assistant", "HUF Sales Analyst", "HUF Stock Analyst"}
FRIENDLY_TOOL_ERROR = "لم أتمكن من جلب هذه البيانات الآن بسبب قيود الصلاحيات أو طريقة الاستعلام. يمكنني المحاولة بطريقة أبسط، مثل تحديد الفترة أو المستودع."
PERMISSION_ERROR_MESSAGE = "لا أملك صلاحية كافية لعرض هذه البيانات حسب صلاحيات حسابك."
TECHNICAL_ERROR_MARKERS = [
    "Blocked SQL keyword detected",
    "SQL keyword blocked",
    "trilogy_erp_database_analyst",
    "TrilogyAi ERP Analytics",
    "Traceback",
    "frappe.exceptions",
    "pymysql",
    "mariadb",
    "OperationalError",
    "ProgrammingError",
    "LiteLLM",
    "BadRequestError",
    "OpenAIException",
    "Invalid type for",
    "tools[",
    "PermissionError",
    "permission_denied",
    "No read permission",
    "not permitted",
]
MODEL_ERROR_MARKERS = [
    "LiteLLM",
    "OpenAI",
    "BadRequestError",
    "APIConnectionError",
    "AuthenticationError",
    "RateLimitError",
    "model_not_found",
    "unsupported model",
    "invalid model",
]


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


def _execution_mode(settings=None):
    settings = settings or get_ai_settings()
    mode = settings.get("chat_execution_mode") or "Native Agent"
    if mode not in ("Native Agent", "Safe ERP Tools", "Advanced ERP Query"):
        return "Native Agent"
    if mode == "Advanced ERP Query" and not settings.get("enable_advanced_erp_query"):
        return "Native Agent"
    return mode


def _get_default_agent(settings=None):
    settings = settings or get_ai_settings()
    for key in ("default_home_agent", "default_agent"):
        if settings.get(key) and frappe.db.exists("Agent", settings.get(key)):
            return settings.get(key)
    if frappe.db.exists("Agent", "HUF Home Assistant"):
        return "HUF Home Assistant"
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


def _field_supported(doctype, fieldname):
    try:
        return frappe.get_meta(doctype).has_field(fieldname)
    except Exception:
        return False


def _model_exists(model_name):
    return bool(model_name and frappe.db.exists("AI Model", model_name))


def _select_model_for_agent(agent_doc, explicit_model=None, settings=None):
    settings = settings or get_ai_settings()
    if explicit_model and _model_exists(explicit_model):
        return explicit_model
    if (
        agent_doc.name in SMART_MODEL_AGENT_NAMES
        and settings.get("use_smart_model_for_analytics", True)
        and _model_exists(settings.get("preferred_smart_model"))
    ):
        return settings.get("preferred_smart_model")
    for key in ("preferred_fast_model", "preferred_agent_model"):
        if _model_exists(settings.get(key)):
            return settings.get(key)
    return agent_doc.model


def _fallback_model_for_agent(agent_doc, settings=None):
    settings = settings or get_ai_settings()
    for key in ("preferred_fast_model", "preferred_agent_model"):
        if _model_exists(settings.get(key)):
            return settings.get(key)
    return agent_doc.model


def _select_agent(agent=None, settings=None):
    agent_name = agent or _get_default_agent(settings)
    if not frappe.db.exists("Agent", agent_name):
        frappe.throw(_("Agent not found"))
    agent_doc = frappe.get_doc("Agent", agent_name)
    if not _is_user_allowed(agent_doc, frappe.session.user):
        frappe.throw(_("You are not authorized to use this agent."), frappe.PermissionError)
    if not _is_admin_or_debug(settings or get_ai_settings()) and agent_doc.name not in SAFE_DEFAULT_AGENT_NAMES:
        frappe.throw(_("You are not authorized to use this agent."), frappe.PermissionError)
    return agent_doc


def _agent_category(agent_doc):
    exact = {
        "HUF Home Assistant": "General",
        "HUF Sales Analyst": "Sales",
        "HUF Stock Analyst": "Stock",
        "HUF Receivables Assistant": "Finance",
        "HUF Task Assistant": "Support",
    }
    if agent_doc.name in exact:
        return exact[agent_doc.name]
    text = " ".join(str(x or "").lower() for x in [agent_doc.name, agent_doc.agent_name, agent_doc.description])
    if "stock" in text or "مخزون" in text:
        return "Stock"
    if "sales" in text or "مبيعات" in text or "customer" in text or "عملاء" in text:
        return "Sales"
    if "receivable" in text or "متأخر" in text or "finance" in text:
        return "Finance"
    if "task" in text or "مهام" in text:
        return "Support"
    if "admin" in text or "database" in text or "sql" in text:
        return "Admin"
    return "General"


def _agent_title(agent_doc):
    titles = {
        "HUF Home Assistant": "مساعد HUF",
        "HUF Sales Analyst": "محلل المبيعات",
        "HUF Stock Analyst": "محلل المخزون",
        "HUF Receivables Assistant": "مساعد المتأخرات",
        "HUF Task Assistant": "مساعد المهام",
    }
    return titles.get(agent_doc.name) or titles.get(agent_doc.agent_name) or agent_doc.agent_name or agent_doc.name


@frappe.whitelist()
def get_available_agents():
    _require_login()
    settings = get_ai_settings()
    default_agent = _get_default_agent(settings)
    # Agent names/descriptions are UI configuration, not ERP business data.
    # Read minimally with system access, then filter through _is_user_allowed
    # and the safe default-agent allowlist for normal users.
    rows = frappe.get_all(
        "Agent",
        filters={"allow_chat": 1, "disabled": 0},
        fields=["name", "agent_name", "description", "modified"],
        order_by="modified desc",
        limit_page_length=100,
    )
    agents = []
    for row in rows:
        try:
            doc = frappe.get_doc("Agent", row.name)
            if not _is_user_allowed(doc, frappe.session.user):
                continue
            if not _is_admin_or_debug(settings) and doc.name not in SAFE_DEFAULT_AGENT_NAMES:
                continue
            if not _is_admin_or_debug(settings) and _agent_category(doc) == "Admin":
                continue
            agents.append({
                "name": doc.name,
                "title": _agent_title(doc),
                "description": doc.description or "",
                "category": _agent_category(doc),
                "is_default": doc.name == default_agent,
            })
        except Exception:
            continue
    agents.sort(key=lambda item: (0 if item["is_default"] else 1, item["category"], item["title"]))
    return {"default_agent": default_agent, "agents": agents}


@frappe.whitelist()
def optimize_agent_roles(dry_run=1):
    _require_login()
    if not _is_admin_or_debug(get_ai_settings()):
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    from huf.ai.agent_role_optimizer import sync_default_agent_roles
    return sync_default_agent_roles(dry_run=dry_run)


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


def _recent_context(session_id):
    if not session_id or not frappe.db.exists("Agent Conversation", session_id):
        return {}
    rows = frappe.get_list(
        "Agent Message",
        filters={"conversation": session_id},
        fields=["role", "content", "creation"],
        order_by="creation desc",
        limit_page_length=6,
    )
    recent = list(reversed(rows))
    last_user = next((row.content for row in reversed(recent) if row.role == "user"), "")
    last_assistant = next((row.content for row in reversed(recent) if row.role in ("agent", "assistant")), "")
    return {
        "last_user_message": last_user[:1200],
        "last_assistant_message": last_assistant[:1200],
        "recent_messages": [{"role": row.role, "content": (row.content or "")[:600]} for row in recent],
    }


def _detect_intent(message, recent=None):
    text = str(message or "").lower()
    combined = " ".join([text, str((recent or {}).get("last_user_message") or "").lower(), str((recent or {}).get("last_assistant_message") or "").lower()])
    intent = {}
    if any(term in combined for term in ["اهم 10 عملاء", "أفضل 10 عملاء", "افضل 10 عملاء", "top customers", "top 10 customers"]):
        intent["last_intent"] = "top_customers"
        intent["last_requested_limit"] = 10
    year_match = re.search(r"(20\d{2})", text)
    if year_match:
        intent["period_text"] = message
        intent["year"] = year_match.group(1)
    if any(term in text for term in ["هذا الشهر", "الشهر الحالي", "السنة الحالية", "آخر سنة", "اخر سنة"]):
        intent["period_text"] = message
    return intent


def _context(message, session_id=None, doctype=None, docname=None, metadata=None, settings=None):
    settings = settings or get_ai_settings()
    recent = _recent_context(session_id)
    ctx = {
        "current_user": frappe.session.user,
        "roles": frappe.get_roles(frappe.session.user),
        "allowed_doctypes": settings.get("allowed_doctypes"),
        "blocked_doctypes": settings.get("blocked_doctypes"),
        "schema_matches": search_schema(message, limit=6) if settings.get("enable_rag") else [],
        "conversation_context": recent,
        "detected_intent": _detect_intent(message, recent),
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
    mode = _execution_mode(settings)
    verbosity = (settings or {}).get("answer_verbosity") or "مختصر"
    advanced_note = ""
    if mode != "Advanced ERP Query":
        advanced_note = """
لا تستخدم SQL خام ولا تطلب من أي أداة توليد SQL. استخدم أدوات HUF الأصلية الآمنة فقط إن كانت متاحة، وإن لم تتوفر البيانات فاطلب تحديد الفترة أو المستودع أو نوع المستند.
"""
    return f"""أجب كمسؤول ERP ذكي ومختصر. إذا كان سؤال المستخدم عربياً فأجب بعربية أعمال طبيعية. لا تخترع أرقاماً أو سجلات. استخدم مسار HUF Agent الأصلي وأدواته الآمنة فقط عند الحاجة.
وضع التنفيذ الحالي: {mode}.
مستوى التفصيل المطلوب افتراضياً: {verbosity}.
{advanced_note}

عقد جودة الإجابة:
- ابدأ بالنتيجة مباشرة، وليس بشرح أنك ستفحص البيانات.
- اذكر النطاق بوضوح: الفترة، الفلاتر، وحدود الصلاحيات أو حد الفحص إن وجد.
- الرد الافتراضي مختصر: ملخص قصير + جدول واحد عند الحاجة + 3 ملاحظات كحد أقصى + 3 خطوات تالية كحد أقصى.
- لا تستخدم عبارات حشو مثل "بالتأكيد" أو "سأقوم الآن" أو مقدمات طويلة.
- لا تقترح Excel أو بريد أو إنشاء مهمة أو إجراء غير مدعوم. لا تذكر أسماء أدوات داخلية أو أخطاء تقنية للمستخدم.
- إذا رجعت الأداة بيانات منظمة، استخدم حقول period وsummary وrows وrequested_limit وreturned_count وscanned_count وcap_reached لصياغة جواب دقيق.
- إذا طلب المستخدم 10 ووجدت أقل، قل: "طلبت 10، ووجدت N فقط ضمن الفترة والصلاحيات الحالية." ولا تسمّها قائمة أفضل 10.
- إن كان السؤال ناقصاً، اسأل سؤالاً توضيحياً واحداً فقط.

قوالب مختصرة:
- ملخص المبيعات: الفترة، إجمالي المبيعات، عدد الفواتير، المستحقات، ثم جدول مؤشرات.
- ملخص المخزون: التاريخ/الفلاتر، الكمية الفعلية، الكمية المتوقعة، قيمة المخزون، ثم جدول مختصر.
- أفضل العملاء: الفترة، العدد المطلوب، العدد الموجود، جدول العميل/المبيعات/المستحق/عدد الفواتير.
- الفواتير المتأخرة: العدد، إجمالي المستحق، جدول مختصر بالفواتير وتواريخ الاستحقاق.

تعامل مع الرسائل كسياق مستمر. إذا كانت الرسالة الحالية فترة مثل "خلال سنة 2026" وكانت الرسالة السابقة عن أفضل العملاء، أكمل طلب أفضل العملاء بهذه الفترة.
لا تعتبر الشكاوى أو التصحيحات مثل "وين القائمة" أو "أرسلت لي عميل واحد" أو "ليش ظهر عميل واحد" أوامر حساسة.
لا تقترح تصدير Excel أو إرسال بريد أو إنشاء مهمة إلا عندما تكون الأداة متاحة ومع التأكيد عند الحاجة.
إذا طلب المستخدم 10 نتائج ووجدت أقل، قل العدد الحقيقي وسبب الاحتمال: لا توجد بيانات كافية، الصلاحيات تحد النتائج، أو حد الفحص الآمن.

سياق النظام الآمن:
{safe_ctx[:6000] if isinstance(safe_ctx, str) else json.dumps(safe_ctx, ensure_ascii=False, default=str)[:6000]}

سؤال المستخدم:
{safe_message}
"""


def _looks_inventory_question(message):
    text = (message or "").lower()
    return any(term in text for term in ["مخزون", "المخزون", "الأصناف", "صنف", "item", "stock", "warehouse", "inventory"])


def _friendly_error(message=None, permission=False):
    if permission:
        return PERMISSION_ERROR_MESSAGE
    content = FRIENDLY_TOOL_ERROR
    if _looks_inventory_question(message):
        content += "\n\nجرّب أحد هذه الأسئلة:\n" + "\n".join(f"- {item}" for item in INVENTORY_SUGGESTIONS)
    return content


def _sanitize_assistant_content(content, user_message=None, settings=None, technical_detail=None):
    settings = settings or get_ai_settings()
    text = str(content or "")
    expose = bool(settings.get("expose_tool_errors_to_user")) and _debug_allowed(settings)
    if expose:
        return redact_sensitive_data(text, settings)
    friendly_replacements = {
        "الأداة أشارت": "النتيجة تشير",
        "الأداة أعادت": "النتيجة تعرض",
        "الأداة رجعت": "النتيجة تعرض",
        "استخدمت الأداة": "راجعت البيانات",
        "الأداة": "النظام",
        "tool call": "التحقق",
        "tool": "النظام",
    }
    for old, new in friendly_replacements.items():
        text = text.replace(old, new)
    lowered = text.lower()
    permission = any(marker.lower() in lowered for marker in ["permission_denied", "permissionerror", "no read permission", "not permitted", "لا تملك صلاحية"])
    if technical_detail:
        lowered_detail = str(technical_detail).lower()
        permission = permission or any(marker.lower() in lowered_detail for marker in ["permission_denied", "permissionerror", "no read permission", "not permitted"])
    if any(marker.lower() in lowered for marker in TECHNICAL_ERROR_MARKERS) or technical_detail:
        return _friendly_error(user_message, permission=permission)
    return redact_sensitive_data(text, settings)


def _looks_model_error(content):
    lowered = str(content or "").lower()
    return any(marker.lower() in lowered for marker in MODEL_ERROR_MARKERS)


@frappe.whitelist()
def new_session(agent=None, model=None, title=None):
    _require_login()
    agent_doc = _select_agent(agent, get_ai_settings())
    cm = ConversationManager(agent_name=agent_doc.name, channel="Desk Chat", external_id=frappe.session.user)
    conv = cm.create_new_conversation(title=title or "Trilogy Ai Chat")
    if model:
        frappe.db.set_value("Agent Conversation", conv.name, "model", model)
    _audit("new_session", session=conv.name, input_summary=title or "")
    return {"session_id": conv.name, "title": conv.title, "agent": conv.agent, "model": model or conv.model, "execution_mode": _execution_mode(get_ai_settings())}


@frappe.whitelist()
def get_ui_config():
    language = getattr(frappe.local, "lang", None) or "en"
    rtl = str(language).startswith("ar")
    labels = {
        "title": "مساعد HUF الذكي" if rtl else "HUF Assistant",
        "subtitle": "اسأل عن المبيعات، المخزون، الفواتير، أو المهام" if rtl else "Ask about sales, stock, invoices, or tasks",
        "empty_title": "كيف أستطيع مساعدتك؟" if rtl else "How can I help?",
        "empty_text": "اسألني عن بيانات ERPNext أو اطلب تلخيصًا أو إجراءً آمنًا." if rtl else "Ask about ERPNext data, summaries, or safe actions.",
        "new_chat": "محادثة جديدة" if rtl else "New Chat",
        "clear": "مسح" if rtl else "Clear",
        "send": "إرسال" if rtl else "Send",
        "close": "إغلاق" if rtl else "Close",
        "expand": "فتح الصفحة الكاملة" if rtl else "Open full page",
        "advanced": "خيارات متقدمة" if rtl else "Advanced Options",
        "agent": "الوكيل" if rtl else "Agent",
        "default_agent_label": "مساعد HUF" if rtl else "HUF Assistant",
        "advanced_hint": "سيتم استخدام الوكيل والنموذج الافتراضيين ما لم يتم تحديد غير ذلك من الإعدادات." if rtl else "The default agent and model will be used unless configured otherwise.",
        "show_details": "إظهار التفاصيل" if rtl else "Show Details",
        "hide_details": "إخفاء التفاصيل" if rtl else "Hide Details",
        "details": "التفاصيل" if rtl else "Details",
        "thinking": "جاري التفكير..." if rtl else "Thinking...",
        "feedback_saved": "تم تسجيل ملاحظتك" if rtl else "Feedback saved",
        "placeholder": "اكتب سؤالك هنا…" if rtl else "Ask HUF Assistant…",
        "composer_hint": "مثال: اعرض مبيعات هذا الشهر أو لخص حالة المخزون" if rtl else "Example: show this month's sales or summarize inventory",
        "more_prompts": "عرض المزيد" if rtl else "Show more",
        "less_prompts": "عرض أقل" if rtl else "Show less",
        "agent_changed": "تم بدء محادثة جديدة مع" if rtl else "Started a new chat with",
        "agent_default_description": "مساعد عام لأسئلة ERPNext اليومية" if rtl else "General assistant for daily ERPNext questions",
        "retry": "إعادة المحاولة" if rtl else "Retry",
        "loading": "جاري التحميل..." if rtl else "Loading...",
        "error": "تعذر الحصول على رد الآن. حاول مرة أخرى أو تواصل مع المسؤول." if rtl else "Unable to get a response now. Try again or contact your administrator.",
    }
    prompts = [
        "اعرض مبيعات هذا الشهر",
        "لخص حالة المخزون",
        "ما الفواتير المتأخرة؟",
        "أنشئ مهمة متابعة للعميل",
        "اقترح تحسينات على التدفق النقدي",
    ] if rtl else [
        "Show this month's sales",
        "Summarize inventory status",
        "Which invoices are overdue?",
        "Create a customer follow-up task",
        "Suggest cash-flow improvements",
    ]
    if frappe.session.user == "Guest":
        return {
            "enabled": False,
            "enable_chat_widget": False,
            "show_home_chat": False,
            "debug_available": False,
            "rtl": rtl,
            "language": language,
            "suggested_prompts": prompts,
            "suggested_prompt_groups": SUGGESTED_PROMPT_GROUPS if rtl else [],
            "can_select_agent": False,
            "can_select_model": False,
            "default_title": labels["title"],
            "labels": labels,
        }
    settings = get_ai_settings()
    admin_or_debug = _is_admin_or_debug(settings)
    available_agents = get_available_agents()
    return {
        "enabled": bool(settings.get("enable_chat_widget", True)),
        "enable_chat_widget": bool(settings.get("enable_chat_widget", True)),
        "show_home_chat": bool(settings.get("show_home_chat", True)),
        "debug_available": _debug_allowed(settings),
        "rtl": rtl,
        "language": language,
        "suggested_prompts": prompts,
        "suggested_prompt_groups": SUGGESTED_PROMPT_GROUPS if rtl else [],
        "can_select_agent": len(available_agents.get("agents", [])) > 1,
        "can_select_model": admin_or_debug,
        "default_agent": available_agents.get("default_agent"),
        "agents": available_agents.get("agents", []),
        "default_title": labels["title"],
        "execution_mode": _execution_mode(settings),
        "labels": labels,
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
    ctx = _context(message, session_id=session_id, doctype=doctype, docname=docname, metadata=metadata, settings=settings)
    execution_mode = _execution_mode(settings)
    selected_model = _select_model_for_agent(agent_doc, explicit_model=model, settings=settings)
    try:
        result = run_agent_sync(agent_name=agent_doc.name, prompt=_format_prompt(message, ctx, settings), provider=agent_doc.provider, model=selected_model, channel_id="Desk Chat", external_id=frappe.session.user, conversation_id=session_id)
    except Exception as exc:
        primary_error = str(exc)
        fallback_model = _fallback_model_for_agent(agent_doc, settings)
        if fallback_model and fallback_model != selected_model:
            try:
                result = run_agent_sync(agent_name=agent_doc.name, prompt=_format_prompt(message, ctx, settings), provider=agent_doc.provider, model=fallback_model, channel_id="Desk Chat", external_id=frappe.session.user, conversation_id=session_id)
                _audit("send_message", status="Success", session=session_id, input_summary=message, metadata={"agent": agent_doc.name, "primary_model": selected_model, "fallback_model": fallback_model, "execution_mode": execution_mode, "primary_error": primary_error[:500]})
                selected_model = fallback_model
            except Exception as fallback_exc:
                latency_ms = int((time.time() - start) * 1000)
                technical = frappe.get_traceback()
                frappe.log_error(technical, "HUF Desk Chat Error")
                _audit("send_message", status="Failed", session=session_id, input_summary=message, output_summary=str(fallback_exc), metadata={"agent": agent_doc.name, "model": selected_model, "fallback_model": fallback_model, "execution_mode": execution_mode, "technical_error": str(fallback_exc), "primary_error": primary_error}, latency_ms=latency_ms)
                content = _sanitize_assistant_content("", message, settings, technical_detail=str(fallback_exc))
                return {"session_id": session_id, "message_id": None, "content": content, "rendered_content": content, "debug_available": _debug_allowed(settings), "requires_confirmation": False, "confirmation": None, "metadata": {"agent": agent_doc.name, "model": fallback_model, "primary_model": selected_model, "model_fallback": True, "execution_mode": execution_mode, "latency_ms": latency_ms}}
        else:
            latency_ms = int((time.time() - start) * 1000)
            technical = frappe.get_traceback()
            frappe.log_error(technical, "HUF Desk Chat Error")
            _audit("send_message", status="Failed", session=session_id, input_summary=message, output_summary=str(exc), metadata={"agent": agent_doc.name, "model": selected_model, "execution_mode": execution_mode, "technical_error": str(exc)}, latency_ms=latency_ms)
            content = _sanitize_assistant_content("", message, settings, technical_detail=str(exc))
            return {"session_id": session_id, "message_id": None, "content": content, "rendered_content": content, "debug_available": _debug_allowed(settings), "requires_confirmation": False, "confirmation": None, "metadata": {"agent": agent_doc.name, "model": selected_model, "execution_mode": execution_mode, "latency_ms": latency_ms}}
    conversation_id = result.get("conversation_id") or session_id
    assistant = _latest_assistant_message(conversation_id) if conversation_id else None
    content = result.get("response") or result.get("content") or (assistant.content if assistant else "تم تنفيذ الطلب، لكن لم يتم توليد نص واضح.")
    raw_content = content
    fallback_model = _fallback_model_for_agent(agent_doc, settings)
    if _looks_model_error(raw_content) and fallback_model and fallback_model != selected_model:
        try:
            result = run_agent_sync(agent_name=agent_doc.name, prompt=_format_prompt(message, ctx, settings), provider=agent_doc.provider, model=fallback_model, channel_id="Desk Chat", external_id=frappe.session.user, conversation_id=conversation_id)
            selected_model = fallback_model
            conversation_id = result.get("conversation_id") or conversation_id
            assistant = _latest_assistant_message(conversation_id) if conversation_id else None
            content = result.get("response") or result.get("content") or (assistant.content if assistant else "تم تنفيذ الطلب، لكن لم يتم توليد نص واضح.")
            raw_content = content
        except Exception as fallback_exc:
            _audit("send_message", status="Failed", session=conversation_id, input_summary=message, output_summary=str(fallback_exc), metadata={"agent": agent_doc.name, "primary_model": selected_model, "fallback_model": fallback_model, "technical_error": str(fallback_exc)})
    content = _sanitize_assistant_content(content, message, settings)
    latency_ms = int((time.time() - start) * 1000)
    message_id = assistant.name if assistant else None
    run_id = result.get("agent_run_id") or result.get("run_id")
    _audit("send_message", session=conversation_id, message=message_id, input_summary=message, output_summary=content, metadata={"run_id": run_id, "context_summary": redact_sensitive_data(ctx, settings)[:2000], "agent": agent_doc.name, "model": selected_model, "execution_mode": execution_mode, "raw_response_preview": str(raw_content)[:1000]}, latency_ms=latency_ms)
    return {"session_id": conversation_id, "message_id": message_id, "content": content, "rendered_content": content, "debug_available": _debug_allowed(settings), "requires_confirmation": False, "confirmation": None, "metadata": {"run_id": run_id, "agent": agent_doc.name, "model": selected_model, "execution_mode": execution_mode, "latency_ms": latency_ms}}


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
