# Execution and acceptance log

Scope: existing HUF feature/system-guide; explicit verified Development site only. No reinstall, framework upgrade, other-site metadata writes or canonical-memory edits. Existing baseline bc2a01dae01db07562d96a77b207f9a5b1f3a620 matched remote and was clean. The Nginx host/site header and existing site root were verified before backup/schema changes. Existing apps were verified as HUF1.0.0-beta.4, Compendium16.2.0, Frappe16.52.0.

| Command/check | Exit | Cases | Failures | Errors | Skips |
|---|---|---|---|---|---|
| Native backup with files, explicit site | 0 | 4 nonempty artifacts; contents not read | 0 | 0 | 0 |
| huf.guide.install.prepare, additive owned-schema sync | 0 | HUF Guide Settings/Binding only | 0 | 0 | 0 |
| Initial native suite | 1 | 18 completed; UX class setup failed | 1 | 2 | 0 |
| Corrected native run | 0 | 30 | 0 | 0 | 0 |
| Final expanded native run | 0 | 32 | 0 | 0 | 0 |
| Ruff0.8.1 check and format check | 0 final | 20 Python files | 0 | 0 | 0 |
| Node syntax / Git whitespace | 0 | edited JavaScript and source diff | 0 | 0 | 0 |
| Focused native esbuild, huf app, under bench_build lock | 0 | Guide JS/CSS/RTL; no full React rebuild needed | 0 | 0 | 0 |
| Second prepare/snapshot check | 0 | existing settings preserved,0 duplicated bindings/tours | 0 | 0 | 0 |
| Shared web HUP expressly approved for this batch | 0 | same master,5 new workers,0 old workers | 0 | 0 | 0 |
| Initial browser run | 1 | 21 assertions passed; network sentinel failed | 0 assertions | 0 page errors | 0 |
| Corrected full browser run | 0 | 21 | 0 | 0 | 0 |

Initial native failures exposed a product upgrade default issue: Frappe converts an absent Check field to0 before a Singles row exists. Preparation now checks actual row existence, preserving deliberately saved0 and installing defaults only for missing rows. Retry succeeded. Earlier Ruff checks stopped on two style findings and one wrong working directory before runtime changes; corrected checks pass.

The initial browser fixture reused its passive external-image sentinel article as a native Markdown form. That editor attempted tracking.invalid twice; the browser blocked both and the strict run failed. A separate clean saved-form fixture now isolates the record-check journey, while the guide article retains the sentinel. The corrected21-case run reports0 external attempts,0 asset failures and0 page errors. No network assertion was removed or relaxed. No Compendium source was modified.

The shared HUP was approved after disclosure of dev.maward.org and test.maward.org sharing the web service and the30-second graceful timeout. Only the verified frappe-owned Gunicorn master was signalled. Read-only Supervisor status was access-denied; no Supervisor privilege escalation or bypass was attempted. Native Gunicorn HUP used the explicitly authorised, independently verified process identity and ownership. No database, Redis, scheduler or other service restart occurred. Target-site translation/Guide Settings metadata caches were cleared for updated UI copy.

Credentials live in Node memory and native helper stdin only. No saved auth state, cookies, tokens, HAR, private session stores or business-document exports. Employee reader and contributor are non-administrative; a third disposable existing-role System Manager persona tests settings. Record checks are temporarily enabled only during owned fixture cases and restored by cleanup. No existing user receives roles. Synthetic mandatory-title gaps are created only in owned disposable records, never customer data.

The check gateway uses full native document permission hooks, including scope/owner/User Permissions and field read levels/masking; a partial document is not substituted for ACL checks. Only the explicitly allowed field projection reaches a registered read-only check; no document/field values return to the panel. The generic check reports presence of selected unconditional mandatory fields, not business completion. Custom business checks remain trusted installed domain-app registrations, never executable settings.

Independent native tests isolate role withdrawal and unpublication. The browser unpublication case follows role withdrawal and is not represented as an independent positive-role unpublication proof. Two-site synthetic isolation, a real approved business procedure/Owner UAT, Production, new domain-rule acceptance and full legacy HUF suites remain NOT_RUN. English phone-specific acceptance is NOT_RUN. Native field access guards are source-verified; a separate real protected-field browser persona is NOT_RUN.

Final admin addition proof: two cases PASS, exit0, including UI creation from Settings→Service Bindings, article/tour/destination entry, a visible accessible Save button, native savedocs HTTP200, a persisted clean Form and readiness result for the newly created binding. The earlier CSS selector/last-field timing did not dispatch a save; correction commits the last field with Tab, waits native requests and uses the accessible Save button. No Frappe change or permission expansion. A bounded keyboard-save diagnostic also passed; the final strict test has no keyboard fallback.

One admin runner was interrupted before its report. No owned process remained; its three fixture identities were identified by the generated prefix and exact first-name ownership and removed with the same native helper before retry. Final independent native check proves zero fixture users/roles/contacts/articles/bindings/tours, with record_checks_enabled0. All completed browser cleanups also show zero auth/share/role/preference rows. Final article copy was updated to the actual three-entry UI and re-read through Compendium in Arabic.

Coverage is22 unique passing browser cases:21 in a complete run plus2 in the final admin-only run, with the readiness case overlapping. BROWSER.json retains the attempt distinctions. No claim that the first failing/network or interrupted runs passed. All final source checks passed. Source and evidence are published together on the authorised feature branch; develop is unchanged.
