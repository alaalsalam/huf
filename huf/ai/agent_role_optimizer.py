import frappe

from huf.ai.safe_erp_tools import SAFE_TOOL_DEFINITIONS, setup_safe_erp_tools


SAFE_AGENT_DEFINITIONS = [
    {
        "name": "HUF Home Assistant",
        "title": "مساعد HUF",
        "category": "General",
        "description": "مساعد ERP عام آمن للمبيعات والمخزون والفواتير والمهام.",
        "tools": [
            "huf_sales_summary",
            "huf_overdue_invoices",
            "huf_stock_summary",
            "huf_low_stock_items",
            "huf_top_customers",
            "huf_create_followup_task_request",
        ],
    },
    {
        "name": "HUF Sales Analyst",
        "title": "محلل المبيعات",
        "category": "Sales",
        "description": "تحليل المبيعات والعملاء والفواتير وأفضل العملاء.",
        "tools": ["huf_sales_summary", "huf_top_customers", "huf_overdue_invoices"],
    },
    {
        "name": "HUF Stock Analyst",
        "title": "محلل المخزون",
        "category": "Stock",
        "description": "تحليل المخزون والمستودعات والأصناف منخفضة الكمية.",
        "tools": ["huf_stock_summary", "huf_low_stock_items"],
    },
    {
        "name": "HUF Receivables Assistant",
        "title": "مساعد المتأخرات",
        "category": "Finance",
        "description": "متابعة الفواتير المتأخرة والمستحقات واقتراحات التحصيل.",
        "tools": ["huf_overdue_invoices", "huf_top_customers", "huf_create_followup_task_request"],
    },
    {
        "name": "HUF Task Assistant",
        "title": "مساعد المهام",
        "category": "Support",
        "description": "تجهيز طلبات مهام المتابعة مع التأكيد قبل أي إنشاء فعلي.",
        "tools": ["huf_create_followup_task_request"],
    },
]


BASE_PROMPT = """
أنت {title} داخل Trilogy Ai / HUF على ERPNext.

قواعد الذكاء وتجربة المستخدم:
- إذا كتب المستخدم بالعربية، أجب بالعربية. وإذا كتب بالإنجليزية، أجب بالإنجليزية.
- افهم المحادثة كسياق مستمر، وليس كل رسالة منفصلة.
- إذا سأل المستخدم "خلال سنة 2026" بعد سؤال عن العملاء، فافهم أنها فترة للسؤال السابق.
- إذا قال المستخدم "وين القائمة؟" أو "أرسلت لي عميل واحد"، فهذا تصحيح أو شكوى وليس أمرًا حساسًا.
- لا تطلب تأكيدًا إلا عند وجود فعل تنفيذي حساس: حذف، اعتماد، إلغاء، إرسال بريد/رسالة، إنشاء أو تعديل مستند فعلي، تغيير صلاحيات، أو تعديل مالي/HR.
- لا تخترع أرقامًا. اعرض فقط ما رجع من الأدوات أو ما تسمح به صلاحيات المستخدم.
- عند طلب أفضل 10 ووجدت أقل، قل بوضوح: "وجدت N فقط ضمن الفترة والصلاحيات الحالية".
- لا تقل "أفضل 10" إذا وجدت عميلاً واحدًا فقط.
- لا تقترح تصدير Excel أو إرسال بريد أو إنشاء مهمة إلا إذا كانت الأداة متاحة، ومع التأكيد عند الحاجة.
- لا تعرض أسماء الأدوات الداخلية أو stack traces أو أخطاء SQL للمستخدم.
- استخدم جداول واضحة وقصيرة، واذكر الفترة المستخدمة وحد الفحص إن كان مؤثرًا.

سلوك أدوات مهمة:
- أسئلة المبيعات: استخدم أداة ملخص المبيعات.
- أفضل العملاء: إذا لم يحدد المستخدم فترة، اسأل سؤالًا واحدًا عن الفترة. إذا أجاب بفترة لاحقًا، أكمل نفس الطلب.
- "خلال سنة 2026" تعني من 2026-01-01 إلى تاريخ اليوم إذا كانت السنة الحالية، إلا إذا قال "كامل سنة 2026".
- "هذا الشهر" من بداية الشهر إلى اليوم.
- "السنة الحالية" من 1 يناير إلى اليوم.
- "آخر سنة" آخر 12 شهرًا.
- المخزون: استخدم أدوات المخزون الآمنة فقط.
- الفواتير المتأخرة: استخدم أداة الفواتير المتأخرة.

صيغة الرد:
1. نتيجة مختصرة.
2. جدول عند وجود بيانات.
3. تفسير قصير إذا النتائج أقل من المطلوب.
4. 2-3 اقتراحات متابعة مدعومة فقط.
"""


def _meta_has(doctype, fieldname):
    try:
        return frappe.get_meta(doctype).has_field(fieldname)
    except Exception:
        return False


def _ensure_gpt55_model():
    provider = frappe.db.exists("AI Provider", "OpenAI")
    if not provider:
        return {"configured": False, "reason": "OpenAI provider not configured."}
    if frappe.db.exists("AI Model", "gpt-5.5"):
        return {"configured": True, "model": "gpt-5.5", "created": False}
    payload = {"doctype": "AI Model", "model_name": "gpt-5.5", "provider": provider}
    for field in ("enabled", "is_enabled", "suitable_for_agents"):
        if _meta_has("AI Model", field):
            payload[field] = 1
    doc = frappe.get_doc(payload)
    doc.flags.ignore_mandatory = True
    doc.flags.ignore_validate = True
    doc.insert(ignore_permissions=True)
    return {"configured": True, "model": doc.name, "created": True}


def _pick_provider_model(settings=None):
    provider = frappe.db.exists("AI Provider", "OpenAI") or frappe.db.get_value("AI Provider", {}, "name")
    current_agent = frappe.db.exists("Agent", "HUF Home Assistant")
    current_model = frappe.db.get_value("Agent", current_agent, "model") if current_agent else None
    preferred = getattr(settings, "preferred_agent_model", None) if settings else None
    model = preferred or current_model or (frappe.db.exists("AI Model", "gpt-5-mini") or frappe.db.get_value("AI Model", {"provider": provider}, "name"))
    return provider, model


def _tool_doc_names():
    names = {}
    for definition in SAFE_TOOL_DEFINITIONS:
        docname = frappe.db.get_value("Agent Tool Function", {"tool_name": definition["tool_name"]})
        if docname:
            names[definition["tool_name"]] = docname
    return names


def _upsert_agent(definition, tool_names, provider, model, dry_run=False):
    docname = frappe.db.exists("Agent", definition["name"]) or frappe.db.get_value("Agent", {"agent_name": definition["name"]}, "name")
    action = "update" if docname else "create"
    if dry_run:
        return {"agent": definition["name"], "action": action, "tools": definition["tools"]}
    payload = {
        "agent_name": definition["name"],
        "provider": provider,
        "model": model,
        "temperature": 0.2,
        "top_p": 1,
        "disabled": 0,
        "allow_chat": 1,
        "allow_guest": 0,
        "persist_conversation": 1,
        "prompt_mode": "Local",
        "instructions": BASE_PROMPT.format(title=definition["title"]),
        "description": definition["description"],
        "history_limit": 6,
        "max_turns": 7,
        "max_knowledge_tokens": 1800,
        "show_tool_execution_details": 0,
    }
    doc = frappe.get_doc("Agent", docname) if docname else frappe.get_doc({"doctype": "Agent"})
    doc.update(payload)
    doc.set("agent_tool", [])
    for tool_name in definition["tools"]:
        if tool_name in tool_names:
            doc.append("agent_tool", {"tool": tool_names[tool_name]})
    doc.save(ignore_permissions=True) if docname else doc.insert(ignore_permissions=True)
    return {"agent": doc.name, "action": action, "tools": definition["tools"]}


def sync_default_agent_roles(dry_run=1):
    dry_run = bool(int(dry_run)) if isinstance(dry_run, str) else bool(dry_run)
    report = {"dry_run": dry_run, "agents": [], "model": None, "default_home_agent": None}
    gpt55 = _ensure_gpt55_model() if not dry_run else {"configured": bool(frappe.db.exists("AI Model", "gpt-5.5")), "model": "gpt-5.5", "dry_run": True}
    report["gpt_5_5"] = gpt55
    if not dry_run:
        setup_safe_erp_tools()
    settings = frappe.get_single("HUF AI Settings") if frappe.db.exists("DocType", "HUF AI Settings") else None
    provider, model = _pick_provider_model(settings)
    report["model"] = {"provider": provider, "selected_model": model, "gpt_5_5_available": bool(frappe.db.exists("AI Model", "gpt-5.5"))}
    tool_names = _tool_doc_names()
    for definition in SAFE_AGENT_DEFINITIONS:
        report["agents"].append(_upsert_agent(definition, tool_names, provider, model, dry_run=dry_run))
    if settings and not dry_run:
        settings.default_home_agent = "HUF Home Assistant"
        if _meta_has("HUF AI Settings", "safe_tool_max_scan_records") and not settings.safe_tool_max_scan_records:
            settings.safe_tool_max_scan_records = 5000
        if _meta_has("HUF AI Settings", "preferred_agent_model") and not settings.preferred_agent_model:
            # Keep current tested model as fallback; gpt-5.5 is registered but not forced.
            settings.preferred_agent_model = model
        if _meta_has("HUF AI Settings", "default_reasoning_effort") and not settings.default_reasoning_effort:
            settings.default_reasoning_effort = "medium"
        if _meta_has("HUF AI Settings", "default_text_verbosity") and not settings.default_text_verbosity:
            settings.default_text_verbosity = "low"
        settings.save(ignore_permissions=True)
        frappe.db.commit()
        report["default_home_agent"] = settings.default_home_agent
    return report
