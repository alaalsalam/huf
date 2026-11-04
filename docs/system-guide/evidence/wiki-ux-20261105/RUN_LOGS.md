# Wiki integration and guide usability

Target: Development `dev.mwe-mis.maward.org`, existing frappe-bench, user frappe.
Baseline HUF: feature/system-guide@ae8d19c0ff2009362555535c2f75a0f2d4f410c1.

Owner request: improve the employee journey and use existing application/screen Wiki manuals without duplicate knowledge maintenance. No AI activation, business-record reads, role expansion, Wiki core modification, shared service restart or business writes are included.

Reproduced baseline (native, read-only): installed Wiki3.2.1/Frappe16.52.0; five Wiki spaces, only CRMS and AMS are application User Manuals. CRMS has62 published reader pages. The71 bindings read Compendium exclusively; Customer List prioritizes registration over its screen manual, and Utility Service Request prioritizes a new-connection procedure over its general screen guide. Guide source links always invoke the Desk router, which cannot open a Wiki website route correctly. The native Wiki search index exists; its snippets can precede current manual revisions, so permission/publication and displayed text must be rechecked from current documents.

Acceptance: existing Compendium references remain supported; explicit Wiki references use the native Wiki publication/space reader checks, including revocation and unpublished-space denial. Search uses the selected native source without copying articles/indexing them in HUF and emits only current permitted metadata. A screen opens its general manual and preserves native tour/destination actions; other procedures are secondary. Source opens the actual Wiki page while preserving the employee's Desk. AR/EN desktop/mobile and a denied persona are checked. Missing app/screen manuals remain explicit gaps. Concurrent CRMS source/manual review is preserved.

Commands, results, cleanup and publication are appended after execution. This file contains technical evidence, not reader instructions or Owner UAT acceptance.

| Command | Exit | Tests/cases | Failures | Errors | Skips | Boundary |
|---|---|---|---|---|---|---|
| Explicit-site `backup --ignore-backup-conf` | 0 | database backup | — | — | — | Private native backup 20261105_024514; contents not opened/committed |
| Native reload of `huf_guide_settings` and `huf_guide_binding` | 0 | 2 DocTypes | 0 | 0 | 0 | Explicit Development only; existing settings retained |
| `bench --site dev.mwe-mis.maward.org execute huf.guide.tests.run.run` initial/final | 0/0 | 41/41 | 0/0 | 0/0 | 0/0 | Rollback; original32 +9 Wiki cases; counts match |
| Wiki migration preview/apply/idempotence/concurrent-edit rejection | 0 | 4 | 0 | 0 | 0 | All70 binding transitions were rolled back; nothing applied persistently |
| CRMS content `unittest crms.tests.test_system_guide_articles` | 0 | 6 | 0 | 0 | 0 | Source compilation, not a business transaction suite |
| Normal pre-commit for owned product/CRMS source | 0 final | Applicable hooks | 0 final | 0 | Nonmatching file-type hooks only | Initial formatting corrections and a delegate-recognition warning were fixed and rechecked; no guard/baseline disabled |
| `bench build --app huf` | 0 | assets/SPA/translations | — | — | — | Existing upstream build warnings retained; no dependency upgrade |
| Normal pre-commit for new browser tools | 0 final | Applicable hooks | 0 final | 0 | Nonmatching hooks only | Corrected fixture error codes and explicit window global before rerun |

Initial whitelist heuristic warnings identified `check_record` and the native Compendium wrappers. The endpoint now explicitly enforces guide access; the wrappers explicitly check Compendium's canonical page permission before calling the original entrypoint. The native denial tests were rerun, and all41 passed. No repository hook path or baseline was weakened.

Published implementation: HUF feature/system-guide@f3efdc34385a99ef3c18c7cf9cf5caa3ee40e3c3 and CRMS version-9@361919caf255f3604e52ad8a14f74ae73ccdbe51, each confirmed against `git ls-remote`. Concurrent CRMS work advanced afterward and remains intact.

Runtime state before the requested web-load window: zero persisted `wiki:` bindings, saved search_source empty (backward-compatible Compendium), guide_only, record_checks_enabled0, AI Provider/AI Model/Agent/Agent Run rows0, owned huf.wiki fixture users0. No browser fixture creation/execution, service signal or persistent Wiki-source switch has occurred. Shared web HUP approval is pending; previous batch approvals were not reused. Browser scenarios and cleanup are prepared in scripts/guide_wiki_browser.cjs and guide_wiki_accounts.py.

Owner subsequently approved the specific shared-web HUP. Supervisor's socket refused this user; no privilege was added. The supported Gunicorn HUP signal was sent to the verified frappe-owned master whose cwd/command matched this Bench; the master remained and all five worker PIDs changed. WEB_LOAD.json records the receipt. Python loading is additionally demonstrated by revision system-guide-wiki-v3 in all three browser personas.

Applied only to the explicit Development site: selected Wiki with the existing user-manual routes crms and ams, saved70 existing bindings to their current source_path-matched Wiki routes, retained the original tour/binding IDs, and verified repeat_pending0. APPLIED.json records the mapping. All existing Compendium pages remain; no Wiki content/roles or business records were changed.

Browser initial: exit1,12 cases,11 passed;0 page errors, asset errors or external attempts. The single assertion incorrectly required pathname /desk/customer, while native Frappe uses /desk/selling/customer. The corrected comparison records the same pathname and native List/Customer/List identity before/after opening the Wiki reader. Focused repeat: exit0,3 cases passed (screen opening/actions, source link, mobile layout). Twelve unique cases now pass; this is not a claim of one all-green full-matrix rerun. BROWSER_INITIAL.json preserves the original result; BROWSER.json is the focused run; BROWSER_SUMMARY.json composes the latest outcome per case.

Visual review of the initial screenshots also found an oversized duplicated article heading. Removed the matching duplicated h1 and scoped the heading/table/image sizes to the panel. Rebuilt only the native HUF guide bundles with node esbuild --apps huf (exit0), then explicit-site clear-cache (exit0); no second Python change/HUP. Applicable JS hooks passed after formatter correction, followed by a passing isolated formatter rerun. The focused desktop/mobile renders were visually inspected. HTTP_ASSETS.json proves200 and byte equality for the current JS/CSS bundles; the initial EN control/render case remains from before this small typography adjustment.

Both browser runs removed their fixture identities, shares, roles attached to those identities, Auth rows, contacts and preferences; final owned counts0. RUNTIME_FINAL.json additionally checks no remaining owned users/contacts and confirms guide_only with record checks disabled and model/agent rows0. Fixtures used existing roles only; no Core assignments or real employee grants were added. The remaining current manual and form/Submit/SIT/Owner-UAT coverage is not closed by these guide checks.

Post-load health: dev.mwe-mis.maward.org and dev.maward.org ping200/pong. test.maward.org returned404 for ping and login; this Bench has no test.maward.org site directory. No pre-load HTTP measurement was captured, so the time/cause of that404 is unproven; it is not reported as a successful Test check or attributed to HUP. Test was not reconfigured or repaired in this scope.
