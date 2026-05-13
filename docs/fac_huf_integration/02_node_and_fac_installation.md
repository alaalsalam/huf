# Phase 2 - Node and FAC Installation Status

Date: 2026-04-30
Branch: feature/huf-fac-erp-copilot
Bench: /home/erpnext/frappe-bench15
HUF app: /home/erpnext/frappe-bench15/apps/huf
FAC app: /home/erpnext/frappe-bench15/apps/frappe_assistant_core

## Git / Working Tree

HUF is on branch `feature/huf-fac-erp-copilot`.

Existing uncommitted HUF work was present before this phase, including chat UX/security files and `docs/fac_huf_integration/`.
No commit was created in this phase.

## Node Environment

Initial shell environment:

- node: v12.22.9
- npm: 8.5.1
- yarn: 1.22.22
- node path: /usr/bin/node
- npm path: /usr/bin/npm
- yarn path: /usr/local/bin/yarn
- nvm directory exists: /home/erpnext/.nvm

Activated user-level Node through nvm:

```bash
export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
nvm install 20
nvm use 20
nvm alias default 20
```

Final build environment used:

- node: v20.20.2
- npm: 10.8.2
- yarn: 1.22.22

Note: Corepack first activated Yarn 4.14.1, which broke Frappe build with a lockfile/workspace error. Yarn was then pinned back to `1.22.22`, which is compatible with this Frappe bench.

## FAC Build

Command:

```bash
bench build --app frappe_assistant_core
```

Result: **Success** after switching to Node 20 and Yarn 1.22.22.

The earlier failed attempt with Yarn 4 returned:

```text
This package doesn't seem to be present in your lockfile; run "yarn install" to update the lockfile
Command 'yarn run build --apps frappe_assistant_core --run-build-command' returned non-zero exit status 1.
```

## Site Discovery / Classification

Existing sites under `/home/erpnext/frappe-bench15/sites` are all real domain-style demo/production sites, for example:

- pro.trilogy-erp.com - sensitive / protected, HUF installed here, FAC must not be installed here.
- restaurants.trilogy-erp.com - sensitive / protected restaurant demo.
- digit.trilogy-erp.com - sensitive / protected.
- asset.trilogy-erp.com, clinic.trilogy-erp.com, med.trilogy-erp.com, hotel.trilogy-erp.com, pos15.trilogy-erp.com, retail.trilogy-erp.com, and others - domain-style demo sites, classified as production/sensitive or unknown for this FAC experiment.

No clearly safe `dev`, `test`, `staging`, or `.local` site was found in this bench.

## FAC Installation

FAC installation status: **Not installed on any site in this phase**.

Reason: no unambiguous safe development site exists in `/home/erpnext/frappe-bench15`, and `pro.trilogy-erp.com` is explicitly protected for this phase.

No `bench --site <site> install-app frappe_assistant_core` was run.
No `bench --site <site> migrate` was run.

## Required Next Environment Step

Create or select a safe development site for FAC, suggested:

```text
huf-fac-dev.localhost
```

Suggested commands for an administrator, only when DB credentials can be supplied securely through prompts and not chat logs:

```bash
cd /home/erpnext/frappe-bench15
bench new-site huf-fac-dev.localhost
bench --site huf-fac-dev.localhost install-app erpnext
bench --site huf-fac-dev.localhost install-app frappe_assistant_core
bench --site huf-fac-dev.localhost migrate
bench --site huf-fac-dev.localhost list-apps
```

Do not use `pro.trilogy-erp.com` for FAC installation.
