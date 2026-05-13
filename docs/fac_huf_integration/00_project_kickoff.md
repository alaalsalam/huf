# ERP AI Copilot Kickoff / بدء المشروع

## العربية

- تاريخ التنفيذ: 2026-04-30
- الفرع الحالي: `feature/huf-fac-erp-copilot`
- حالة Git قبل إنشاء ملفات التوثيق: نظيفة، لا توجد تغييرات ظاهرة في `git status --short`.
- هل HUF موجود؟ نعم. المسار: `/home/erpnext/frappe-bench15/apps/huf`
- مستودع HUF: `https://github.com/tridz-dev/huf.git` عبر remote `upstream`.
- هل FAC تم تنزيله؟ تم تنزيله جزئيًا إلى: `/home/erpnext/frappe-bench15/apps/frappe_assistant_core`.
- هل FAC تم تثبيته على site؟ لا.
- سبب عدم التثبيت: الـ bench يحتوي عدة مواقع، وsite التطوير غير محدد بشكل آمن. HUF مركّب حاليًا على `pro.trilogy-erp.com` فقط، لكنه موقع حساس/محمي في سجل البيئة، لذلك لم يتم تثبيت FAC عليه بدون تأكيد صريح.
- عائق إضافي: `bench get-app` وصل إلى مرحلة build وفشل بسبب Node.js الحالي `v12.22.9` بينما build يتطلب Node `>=18`.
- اسم site المستخدم: لم يتم استخدام site للتثبيت.
- قائمة التطبيقات المثبتة على `pro.trilogy-erp.com` للفحص فقط:
  - `frappe`
  - `erpnext`
  - `hrms`
  - `persona`
  - `translations_ar_eg`
  - `font`
  - `ksa_hr`
  - `hr_ksa`
  - `ksa_compliance`
  - `pro_standard`
  - `change_language`
  - `huf`

## English Brief

- Execution date: 2026-04-30
- Current branch: `feature/huf-fac-erp-copilot`
- Git state before docs: clean.
- HUF exists at `/home/erpnext/frappe-bench15/apps/huf`.
- FAC was cloned/partially installed at bench app level, but asset build failed due Node.js `v12.22.9`; Frappe v15 build requires Node `>=18`.
- FAC was not installed on any site because the bench has multiple sites and no safe development site was selected.

## المشاكل أو العوائق / Blockers

1. Site التطوير غير محدد. يوجد أكثر من site داخل `/home/erpnext/frappe-bench15`.
2. `pro.trilogy-erp.com` هو site HUF الحالي، لكنه مصنف كـ protected/sensitive في ذاكرة المشروع.
3. Node.js الحالي قديم: `v12.22.9`. يلزم Node `>=18` قبل إعادة build لـ FAC.
4. لم يتم تنفيذ `install-app`, `migrate`, أو أي تغيير بيانات ERP.
5. لم يتم وضع أي API keys أو credentials.

## الخطوة التالية المقترحة / Proposed Next Step

1. تحديد site تطوير آمن لتثبيت FAC، أو الموافقة الصريحة على استخدام `pro.trilogy-erp.com`.
2. ترقية/تفعيل Node المناسب للـ bench build، ويفضل Node 18 أو 20 حسب توافق bench.
3. إعادة تشغيل build لـ `frappe_assistant_core` فقط.
4. بعد ذلك فقط: `bench --site <selected-site> install-app frappe_assistant_core` ثم `migrate` عند الحاجة.
5. المرحلة الثانية: إثبات MCP contract بين HUF MCP Client و FAC MCP Server بدون تغيير business logic.
