"""Manager-only configuration diagnostics. No transaction reads or writes."""

from importlib.metadata import version

import frappe
from frappe import _

from huf.guide import checks, context, knowledge


def inspect_services():
	settings = frappe.get_single("HUF Guide Settings")
	source = settings.get("search_source") or "Compendium"
	installed = source.lower() in frappe.get_installed_apps()
	compatible = installed and (
		source == "Wiki" or version("compendium").split(".")[0] == frappe.__version__.split(".")[0]
	)
	search_ready = compatible
	if source == "Wiki" and installed:
		from wiki.frappe_wiki.doctype.wiki_document.wiki_sqlite_search import WikiSQLiteSearch

		from huf.guide.wiki_source import spaces

		search_ready = bool(spaces()) and WikiSQLiteSearch().index_exists()
	services = []
	for row in frappe.get_list("HUF Guide Binding", fields=["name"], limit_page_length=500):
		binding = frappe.get_doc("HUF Guide Binding", row.name)
		issues = []
		try:
			knowledge.read(binding.article_path)
		except (frappe.PermissionError, frappe.ValidationError, ImportError):
			issues.append(
				_(
					"Publish a permitted article at this path in its native source and check the selected Wiki spaces."
				)
			)
		if not context.screen_allowed(
			{"screen_type": binding.screen_type, "screen_name": binding.screen_name}
		):
			issues.append(_("Select an existing, permitted screen."))
		if binding.form_tour:
			try:
				if not context.permitted_tour(binding):
					issues.append(_("Choose a read-only Form Tour for this exact screen."))
			except frappe.DoesNotExistError:
				issues.append(_("Create the missing Form Tour or remove its reference."))
		if binding.target_type and not context.permitted_action(
			binding, {"screen_type": binding.screen_type, "screen_name": binding.screen_name}
		):
			issues.append(_("Correct the destination screen or readable field and review screen exclusions."))
		if not binding.next_instruction:
			issues.append(_("Add the approved next instruction from the source article."))
		if binding.record_check_enabled:
			try:
				checks.definition(binding)
				if not binding.check_roles:
					issues.append(_("Select existing roles for the optional record check."))
			except frappe.ValidationError:
				issues.append(
					_(
						"Register the domain check and match its explicit fields, or disable the service check."
					)
				)
		services.append(
			{
				"binding": binding.name,
				"enabled": bool(binding.enabled),
				"screen": binding.screen_name,
				"ready": not issues,
				"issues": issues,
			}
		)
	return {
		"source": source,
		"installed": installed,
		"compatible": compatible,
		"search_ready": search_ready,
		"services": services,
		"record_checks_enabled": bool(
			frappe.db.get_single_value("HUF Guide Settings", "record_checks_enabled")
		),
		"limit": 500,
	}
