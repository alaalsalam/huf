# HUF Enhanced AI Chat QA Checklist

## Normal User
- Open `/app/huf-chat` after login.
- Confirm only own sessions appear.
- Send a general Arabic question and confirm a concise response is stored.
- Confirm Debug is hidden.
- Try reading another user's session URL/API and confirm permission is denied.

## Accounts User
- Ask: `ما الفواتير المتأخرة؟`
- Ask: `اعرض أعلى العملاء حسب المستحقات`.
- Confirm results use permitted accounting DocTypes only.
- Request a payment or invoice submission and confirm it requires confirmation.

## Sales User
- Ask: `اعرض مبيعات هذا الشهر`.
- Ask: `ما العملاء الذين يحتاجون متابعة؟`
- Confirm Sales Invoice/Sales Order access respects the user's ERP permissions.

## HR User
- Ask for non-sensitive HR summaries only if the role has permission.
- Request salary, employee private data, or payroll changes and confirm access is blocked or confirmation is required.

## System Manager
- Confirm `/app/huf-chat` loads.
- Enable debug in `HUF AI Settings` and confirm Debug is visible.
- Confirm `get_debug_trace` works only for authorized roles.
- Review `HUF AI Audit Log` entries after chat and confirmation actions.

## Arabic and RTL
- Confirm widget and page align RTL for Arabic users.
- Confirm suggested Arabic prompts render correctly.
- Confirm Arabic responses do not overlap UI controls.

## Sensitive Action Confirmation
- Try delete, submit, cancel, send email, payment, salary, User, Role, permission, GL Entry, Journal Entry, Sales Invoice, and Purchase Invoice actions.
- Confirm `requires_confirmation=true` before execution.
- Confirm another user cannot replay the confirmation.
- Confirm used or expired confirmations cannot be reused.

## Debug Visibility
- Normal user: no Debug button and API returns permission error.
- System Manager/debug role: Debug button appears only when backend returns `debug_available=true`.

## Redaction
- Include emails, phone numbers, API keys, bearer tokens, and passwords in a prompt.
- Confirm provider context and audit summaries redact sensitive values.
- Confirm permissions still work after redaction.

## RAG and Schema Retrieval
- Search schema for `Sales Invoice`, `Customer`, and `Item`.
- Confirm blocked DocTypes such as `User`, `Role`, `DocPerm`, `System Settings`, OAuth, Integration Request, Error Log, HR salary, and GL Entry do not appear for AI access.
- Confirm allowed DocTypes, when configured, restrict both schema and data retrieval.
