# Phase 2 Production - FAC Installation on pro.trilogy-erp.com

Date: 2026-04-30
Target site: `pro.trilogy-erp.com`
Bench: `/home/erpnext/frappe-bench15`
HUF branch: `feature/huf-fac-erp-copilot`

## Scope

Owner explicitly approved installing Frappe Assistant Core on the sensitive production-like site `pro.trilogy-erp.com`.

This phase only installed and validated FAC availability. It did not create HUF MCP records, OAuth clients, API keys, tokens, FAC tool calls, reports, CRUD actions, workflow actions, or HUF/FAC integration logic.

## Environment

- User: `erpnext`
- Host: `vmi1295991.contaboserver.net`
- Node before nvm activation: `v12.22.9`
- Node used via nvm: `v20.20.2`
- npm: `10.8.2`
- yarn: `1.22.22`
- Required app directories present:
  - `apps/frappe`
  - `apps/erpnext`
  - `apps/huf`
  - `apps/frappe_assistant_core`

## Pre-install Site State

`bench --site pro.trilogy-erp.com list-apps` showed HUF installed and FAC not installed:

```text
frappe             15.17.0 version-15
erpnext            15.16.0 version-15
hrms               15.5.0  version-15
persona            0.0.1   main
translations_ar_eg 0.0.1   main
font               0.0.1   master
ksa_hr             0.0.1   main
hr_ksa             0.0.1   version-15
ksa_compliance     0.35.0  master
pro_standard       0.0.1   main
change_language    0.0.1   main
huf                0.0.1   trilogy-ai-branding
```

`bench --site pro.trilogy-erp.com version` showed `frappe_assistant_core 2.4.1` available in the bench, but it was not installed on the site before this phase.

## Backup

A full backup with files was completed before installation.

Backup timestamp from command session:

```text
BACKUP_TS=20260430_220617
```

Backup files produced:

```text
20260430_230618-pro_trilogy-erp_com-site_config_backup.json
20260430_230618-pro_trilogy-erp_com-database.sql.gz
20260430_230618-pro_trilogy-erp_com-files.tar
20260430_230618-pro_trilogy-erp_com-private-files.tar
```

Backup status: success.

No restore was performed. No backup file was moved or deleted.

## Build Before Install

Command:

```bash
bench build --app frappe_assistant_core
```

Result: success.

Note: asset linking printed an existing non-fatal warning for `doppio/node_modules`, but FAC build completed successfully.

## FAC Installation

Pre-install check:

```text
FAC not installed
```

Command:

```bash
bench --site pro.trilogy-erp.com install-app frappe_assistant_core
```

Result: success.

Notes:
- FAC DocTypes were created/updated.
- Optional OCR model pre-download was skipped because optional OCR dependencies are not installed.
- Non-fatal CSS parser warnings appeared while updating FAC dashboard: `box-shadow: 0 3px 6px #0000001a`.

## Migrate

Command:

```bash
bench --site pro.trilogy-erp.com migrate
```

Result: success.

FAC migration output included plugin initialization:

```text
Plugin system initialized: 1 plugins enabled, 17 tools available
```

## Cache And Post-install Build

Commands:

```bash
bench --site pro.trilogy-erp.com clear-cache
bench --site pro.trilogy-erp.com clear-website-cache
bench build --app frappe_assistant_core
```

Result: success.

No restart was executed.

## Post-install Site State

`bench --site pro.trilogy-erp.com list-apps` now includes FAC:

```text
frappe                15.17.0 version-15
erpnext               15.16.0 version-15
hrms                  15.5.0  version-15
persona               0.0.1   main
translations_ar_eg    0.0.1   main
font                  0.0.1   master
ksa_hr                0.0.1   main
hr_ksa                0.0.1   version-15
ksa_compliance        0.35.0  master
pro_standard          0.0.1   main
change_language       0.0.1   main
huf                   0.0.1   feature/huf-fac-erp-copilot
frappe_assistant_core 2.4.1   main
```

## FAC Endpoint Validation

Expected endpoint:

```text
/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp
```

Code search result: endpoint exists in FAC source, including:

```text
apps/frappe_assistant_core/frappe_assistant_core/api/fac_endpoint.py:253:def handle_mcp()
apps/frappe_assistant_core/frappe_assistant_core/api/fac_endpoint.py:260:Endpoint: /api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp
```

HEAD request:

```bash
curl -I "https://pro.trilogy-erp.com/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp"
```

Result:

```text
HTTP/1.1 401 UNAUTHORIZED
WWW-Authenticate: Bearer realm="Frappe Assistant Core", resource_metadata="https://pro.trilogy-erp.com/.well-known/oauth-protected-resource"
```

This is acceptable for this phase because no token/OAuth setup was performed and the endpoint is protected. It is not a 404.

## Not Performed

- No HUF MCP Server record was created.
- No OAuth client was created.
- No API key or token was added.
- No FAC tools were called.
- No reports, CRUD, workflow actions, or MCP POST requests were executed.
- No restart was executed.
- No commit was created.

## Ready For Phase 3?

Yes, from an installation readiness perspective.

Remaining blockers before real HUF -> FAC connection:

1. Decide production authentication model.
2. Create OAuth/per-user token mapping design.
3. Create HUF MCP server record only in the approved next phase.
4. Sync FAC tools through HUF with namespace `fac`.
5. Keep write tools disabled until HUF confirmation and audit layers are connected.