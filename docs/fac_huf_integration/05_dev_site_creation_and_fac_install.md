# Phase 2.5B - DEV Site Creation and FAC Install

Date: 2026-04-30
Bench: `/home/erpnext/frappe-bench15`
DEV_SITE: `huf-fac-dev.localhost`
HUF branch: `feature/huf-fac-erp-copilot`

## Environment Check

- User: `erpnext`
- Node activated through nvm: `v20.20.2`
- npm: `10.8.2`
- yarn: `1.22.22`
- Required apps present:
  - `apps/frappe`: yes
  - `apps/erpnext`: yes
  - `apps/huf`: yes
  - `apps/frappe_assistant_core`: yes

## Safety Boundaries

- `pro.trilogy-erp.com` was not used.
- No other site was used.
- No `rm -rf` was used.
- No database was dropped.
- No secrets, passwords, tokens, or API keys were printed or stored.
- No commit was created.
- No MCP integration, OAuth client, FAC tool call, CRUD, report, or production data operation was executed.

## Partial Site Handling

Previous partial site directories already existed and were preserved:

```text
sites/huf-fac-dev.localhost.partial.20260430_203345
sites/huf-fac-dev.localhost.partial.20260430_203605
```

During Phase 2.5B, `bench new-site huf-fac-dev.localhost` was attempted again and stopped at the hidden interactive password prompt as required by the safety policy. This produced another incomplete site directory. `bench --site huf-fac-dev.localhost list-apps` failed because the generated database credentials were not usable for a completed site.

The current partial directory was moved safely without delete/drop:

```text
sites/huf-fac-dev.localhost.partial.20260430_210919
```

Values from `site_config.json` were not printed.

## Site Creation

Command attempted:

```bash
bench new-site huf-fac-dev.localhost
```

Result: **Blocked / incomplete**.

Reason: the command requires interactive hidden input for MariaDB root password and Administrator password. Per project rules, these secrets must be entered only through secure terminal takeover and must not be pasted into chat or passed as command-line flags.

## Installation Results

- Site created: no, only partial directories were produced and moved aside
- ERPNext installed: no
- HUF installed: no
- FAC installed: no
- migrate success: no
- build success in this phase: not run after site creation block
- final list-apps: not available because the site was not created

## FAC Endpoint

Expected endpoint after FAC installation:

```text
/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp
```

Endpoint code exists: yes, previously validated in FAC source at:

```text
apps/frappe_assistant_core/frappe_assistant_core/api/fac_endpoint.py
```

curl executed: no. Reason: DEV_SITE was not created and FAC was not installed.

## Problems / Blockers

- Secure terminal input is required for `bench new-site` password prompts.
- Moved partial site directories now present:
  - `sites/huf-fac-dev.localhost.partial.20260430_203345`
  - `sites/huf-fac-dev.localhost.partial.20260430_203605`
  - `sites/huf-fac-dev.localhost.partial.20260430_210919`
- These partial directories should only be cleaned later after explicit owner approval.

## Ready for Phase 3?

No.

Phase 3 can start only after:

1. `huf-fac-dev.localhost` is created through secure terminal takeover.
2. `erpnext`, `huf`, and `frappe_assistant_core` are installed on it.
3. migrate succeeds.
4. list-apps confirms all required apps.
5. FAC endpoint is reachable or at least loadable through the dev site.