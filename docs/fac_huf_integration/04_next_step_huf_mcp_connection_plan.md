# Phase 3 Plan - HUF MCP Connection to FAC

Date: 2026-04-30
Product: ERP AI Copilot = HUF + Frappe Assistant Core

## Architecture Decision

FAC remains the Execution & ERP Tool Layer.
HUF remains the Product, Agent, UX, RAG, Automation, and user-facing orchestration layer.

Target path:

```text
HUF Agent -> HUF MCP Client -> FAC MCP Server -> FAC Tools -> ERPNext/Frappe Permissions/Audit
```

FAC code must not be copied into HUF.

## Prerequisite

A safe development site must exist first, suggested:

```text
huf-fac-dev.localhost
```

FAC must be installed and migrated only on that development site.

## Proposed HUF MCP Server Record

Create a HUF MCP Server record after DEV_SITE is ready:

- name: `fac_erpnext`
- namespace: `fac`
- endpoint: `http://huf-fac-dev.localhost/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp`
- auth: temporary dev-only token if needed
- production auth: per-user OAuth token mapping

## First Tool Sync Targets

Initial FAC tools to discover and test through HUF:

- `fac.report_list`
- `fac.generate_report`
- `fac.list_documents`
- `fac.get_document`

## Safety Rules

- Do not enable write tools before HUF confirmation layer is connected.
- Do not execute destructive actions.
- Respect Frappe permissions through FAC.
- Use audit logs on both layers where available.
- Hide raw tool/internal errors from normal users.
- Production requires per-user OAuth mapping, not one shared long-lived service credential.

## Phase 3 Acceptance Criteria

1. FAC installed on DEV_SITE only.
2. HUF MCP Server record `fac_erpnext` created in DEV_SITE/HUF development context.
3. HUF can sync FAC tools with namespace `fac`.
4. HUF can call read-only FAC tools from a test agent.
5. No write tool is exposed without confirmation.
6. No FAC secrets are committed or printed.﻿﻿

﻿## Validated DEV_SITE

- DEV_SITE = huf-fac-dev.localhost
- ERPNext installed = no
- HUF installed = no
- FAC installed = no
- migrate success = no
- build success = not run after site creation block
- FAC endpoint code exists = yes
- Ready for MCP connection = no
- Remaining blockers = `bench new-site huf-fac-dev.localhost` requires secure interactive MariaDB root password / Administrator password input. Partial site directories were moved aside safely: `sites/huf-fac-dev.localhost.partial.20260430_203345`, `sites/huf-fac-dev.localhost.partial.20260430_203605`, and `sites/huf-fac-dev.localhost.partial.20260430_210919`. Do not enter passwords in chat.

﻿## Validated PRO_SITE

- PRO_SITE = pro.trilogy-erp.com
- FAC installed = yes
- HUF installed = yes
- backup completed = yes
- migrate success = yes
- build success = yes
- FAC endpoint code exists = yes
- curl HEAD status = `401 UNAUTHORIZED`
- Ready for MCP connection = yes, installation prerequisite is ready; integration is intentionally not started yet
- Remaining blockers = production OAuth/per-user token mapping design, HUF MCP Server record creation, FAC tool sync, and write-tool confirmation/audit policy in the next approved phase