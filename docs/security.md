# HUF AI Security

- Guest users are blocked.
- Debug trace is restricted to System Manager, HUF Administrator, or configured debug roles.
- ERP data reads use `frappe.get_list`, `frappe.get_doc`, and `frappe.has_permission`.
- Sensitive actions require explicit confirmation.
- Audit logs record user, session, action, status, summaries, metadata, and latency.
- API keys are never hard-coded and must remain in provider/settings password fields.
