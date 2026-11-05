# Private preparation on an existing Frappe site

The existing repository remains on `develop`; upstream history and authorship are preserved.
For the validated Python 3.14 environment, use `PIP_CONSTRAINT=.../constraints/frappe16.txt`
when installing requirements. Preserve the site's other constraints too. Do not upgrade
shared SDKs as a side effect of installing HUF.

Site settings (defaults retain upstream behaviour):

- `huf_hidden: 1`: hide the app tile and HUF workspace/icons. Direct private UI access
  requires Administrator or an existing System Manager role.
- `huf_auto_assign_roles: 0`: disable automatic user-role grants and backfills, including
  the System Manager backfill. Explicit assignments still use native permissions.
- `huf_background_enabled: 0`: stop only HUF's scheduled jobs after migration and preserve
  the existing Bench-wide scheduler interval. Apply `huf.deployment.apply_site_policy`
  once after initial installation because Frappe synchronizes jobs after install hooks.
- `huf_skip_demo_seeds: 1`: omit unrelated Hub, design-system, meeting and WhatsApp demo seeds.
- `huf_execution_enabled: 0`: refuse agent execution even for the owner while preparation
  is incomplete; it does not block reading configuration. Change explicitly only after
  provider verification and role/permission review.

These flags do not copy keys, contact providers, alter other sites, grant business access,
or activate agents. Application-specific agents/tools belong to the owning application.
Keep them disabled until a real provider/model is configured and approved permission
checks pass. Background jobs require an explicit review before resuming; turning the
flag on does not silently unstop previously stopped jobs.

Use a protected full site backup before install/migrate. For rollback, prefer disabling
new agents and stopping HUF jobs while preserving records; a database restore requires
an approved maintenance window and replaces later changes. Do not uninstall to test rollback.
