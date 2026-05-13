# Initial Architecture Decision / القرار المعماري الأولي

## القرار / Decision

ERP AI Copilot سيكون منتجًا واحدًا يجمع HUF مع Frappe Assistant Core بدون نسخ كود FAC داخل HUF.

## توزيع الأدوار / Layering

- **FAC = Execution & ERP Tool Layer**
  - طبقة تنفيذ وتحليل آمنة للوصول إلى ERPNext/Frappe.
  - مسؤولة عن أدوات ERP، التقارير، قراءة المستندات، واحترام صلاحيات Frappe والتدقيق.

- **HUF = Product, Agent, UX, RAG, Automation Layer**
  - طبقة المنتج النهائية.
  - مسؤولة عن الشات، الوكلاء، RAG، التريجرات، الأتمتة، تجربة المستخدم، وتغليف النتائج بشكل تجاري واضح.

## مسار الاتصال الأساسي / Primary Integration Path

```text
HUF Agent
  -> HUF MCP Client
  -> FAC MCP Server
  -> FAC Tools
  -> ERPNext / Frappe Permissions / Audit
```

## Namespace

سيتم استخدام namespace لأدوات FAC باسم:

```text
fac
```

أمثلة الأدوات الأولية المستهدفة:

- `fac.report_list`
- `fac.generate_report`
- `fac.list_documents`
- `fac.get_document`

## Security & Tokens

- Service token مسموح فقط للتجربة المحلية أو التطوير المحدود.
- الإنتاج يتطلب per-user OAuth token mapping حتى تبقى صلاحيات المستخدم محفوظة end-to-end.
- لا يتم حفظ أو hard-code لأي API keys أو credentials داخل HUF.
- العمليات الحساسة تتطلب confirmation layer من HUF قبل التنفيذ.

## المرحلة الأولى / Phase 1

إثبات أن HUF يستطيع:

1. اكتشاف أدوات FAC عبر MCP.
2. مزامنة تعريفات أدوات FAC داخل HUF Tool Registry باسم `fac.*`.
3. استدعاء أدوات قراءة آمنة مثل التقارير وقوائم المستندات.
4. عرض النتائج داخل تجربة HUF بدون كشف أخطاء داخلية للمستخدم النهائي.

## ما لن يتم الآن / Not Now

- لا نسخ لكود FAC داخل HUF.
- لا تغيير business logic في HUF.
- لا تفعيل OAuth production setup.
- لا تنفيذ عمليات write أو submit أو delete.
- لا تجاوز لصلاحيات Frappe.
