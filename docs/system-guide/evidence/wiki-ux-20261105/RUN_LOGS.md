# Wiki integration and guide usability

Target: Development `dev.mwe-mis.maward.org`, existing frappe-bench, user frappe.
Baseline HUF: feature/system-guide@ae8d19c0ff2009362555535c2f75a0f2d4f410c1.

Owner request: improve the employee journey and use existing application/screen Wiki manuals without duplicate knowledge maintenance. No AI activation, business-record reads, role expansion, Wiki core modification, shared service restart or business writes are included.

Reproduced baseline (native, read-only): installed Wiki3.2.1/Frappe16.52.0; five Wiki spaces, only CRMS and AMS are application User Manuals. CRMS has62 published reader pages. The71 bindings read Compendium exclusively; Customer List prioritizes registration over its screen manual, and Utility Service Request prioritizes a new-connection procedure over its general screen guide. Guide source links always invoke the Desk router, which cannot open a Wiki website route correctly. The native Wiki search index exists; its snippets can precede current manual revisions, so permission/publication and displayed text must be rechecked from current documents.

Acceptance: existing Compendium references remain supported; explicit Wiki references use the native Wiki publication/space reader checks, including revocation and unpublished-space denial. Search uses the selected native source without copying articles/indexing them in HUF and emits only current permitted metadata. A screen opens its general manual and preserves native tour/destination actions; other procedures are secondary. Source opens the actual Wiki page while preserving the employee's Desk. AR/EN desktop/mobile and a denied persona are checked. Missing app/screen manuals remain explicit gaps. Concurrent CRMS source/manual review is preserved.

Commands, results, cleanup and publication are appended after execution. This file contains technical evidence, not reader instructions or Owner UAT acceptance.
