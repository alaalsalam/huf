# changAI and HUF Integration Analysis

## What to take from changAI UX
- Easy entry from Desk through a floating chat button.
- A compact side panel for quick ERP questions.
- A full-page chat route for longer sessions.
- Session history, suggested prompts, and clear loading states.

## What to keep from HUF
- Existing Agent, Agent Conversation, Agent Message, Agent Run, Agent Tool Call, feedback, tools, triggers, RAG, MCP, and observability architecture.
- Existing AI Provider and AI Model configuration.
- Existing permission model and agent access rules.

## What to redesign
- Implement the UX natively in HUF assets and Frappe pages.
- Route all calls through `huf.api.chat`.
- Add schema-aware ERP access through safe Frappe APIs, not raw SQL.
- Add safety confirmation before sensitive mutations.

## Technical risks
- Existing agents may have mutating tools; sensitive actions must be confirmed before execution.
- External AI providers may be unavailable or costly; tests must mock execution.
- Frappe Desk assets must remain lightweight and avoid heavy dependencies.

## Permission and security risks
- Debug traces can expose prompts, tool arguments, and business data, so they are restricted to admin/debug roles.
- ERP reads must respect DocType and document-level permissions.
- Blocked DocTypes prevent accidental exposure of sensitive records.

## Proposed integration plan
- Reuse HUF conversation and run DocTypes.
- Add a unified chat API.
- Add ERP schema RAG and safe read tools.
- Add audit logs, redaction, and pending confirmations.
- Add Desk widget and `/app/huf-chat` page.

## License note
changAI source code must not be copied. This implementation only adopts similar UX patterns and rebuilds them natively inside HUF.
