# Phase 2 - FAC MCP Endpoint Validation

Date: 2026-04-30
Bench: /home/erpnext/frappe-bench15
FAC app path: /home/erpnext/frappe-bench15/apps/frappe_assistant_core

## Expected Endpoint

```text
/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp
```

## Code Evidence

Search results confirmed the endpoint exists in FAC source code:

- `frappe_assistant_core/api/fac_endpoint.py` defines `handle_mcp()`.
- `frappe_assistant_core/utils/cache.py` builds the endpoint URL.
- `frappe_assistant_core/assistant_core/server.py` references the endpoint.
- `frappe_assistant_core/assistant_core/doctype/assistant_core_settings/assistant_core_settings.py` references the endpoint.
- `frappe_assistant_core/core/constants.py` defines `FAC_ENDPOINT`.
- OAuth discovery/CORS modules reference the endpoint.

Representative source paths:

```text
apps/frappe_assistant_core/frappe_assistant_core/api/fac_endpoint.py
apps/frappe_assistant_core/frappe_assistant_core/core/constants.py
apps/frappe_assistant_core/frappe_assistant_core/api/oauth_discovery.py
apps/frappe_assistant_core/frappe_assistant_core/api/oauth_cors.py
```

## Curl / HTTP Validation

HTTP curl was **not executed** against a site because FAC is not installed on a safe DEV_SITE yet.

Reason: all existing sites in the current bench are domain-style production/demo sites or unknown. `pro.trilogy-erp.com` is protected and must not be used for FAC installation or migrate.

## Security Notes

- No OAuth client was created.
- No API key or secret was added.
- No MCP tool call was executed.
- No ERP data was read or modified through FAC.
- Production setup must use per-user OAuth mapping.
- A temporary service token may be used only on a local/dev site for early integration experiments.
