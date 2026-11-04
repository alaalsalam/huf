"""Explicit fresh-install profile. Existing full HUF installations retain their hooks."""

import os

import frappe

from huf.guide.policy import guide_installation


def after_install():
	if os.environ.get("HUF_INSTALL_PROFILE") == "guide_only":
		settings = frappe.get_single("HUF Guide Settings")
		settings.guide_only_install = 1
		settings.mode = "guide_only"
		settings.enabled = 0
		settings.save()
		return
	from huf.install import after_install as full_install

	full_install()


def after_migrate():
	if guide_installation():
		return after_sync()
	from huf.ai.channels.run_as import ensure_all_audit_fields
	from huf.ai.skills.hooks import sync_app_skills
	from huf.install import after_migrate as full_migrate
	from huf.install import seed_voice_engines

	full_migrate()
	sync_app_skills()
	seed_voice_engines()
	ensure_all_audit_fields()


def after_app_install(app_name):
	if guide_installation():
		return
	from huf.ai.app_seeding.seeder import on_app_installed
	from huf.ai.skills.hooks import sync_app_skills
	from huf.install import setup_desktop_icon_as_workspace

	setup_desktop_icon_as_workspace(app_name)
	on_app_installed(app_name)
	sync_app_skills(app_name)


def after_sync():
	"""A fresh guide-only site must not enqueue HUF's optional AI/channel jobs."""
	if not guide_installation():
		return
	jobs = frappe.get_all(
		"Scheduled Job Type", filters={"method": ["like", "huf.%"], "stopped": 0}, pluck="name"
	)
	for name in jobs:
		frappe.db.set_value("Scheduled Job Type", name, "stopped", 1)
	return {"huf_jobs_stopped": len(jobs)}


def seed_example():
	"""Only generic guide content. Create missing rows; never overwrite site edits."""
	frappe.only_for("System Manager")
	name = "HUF Guide Search"
	if not frappe.db.exists("Form Tour", name):
		frappe.get_doc(
			{
				"doctype": "Form Tour",
				"title": name,
				"ui_tour": 1,
				"view_name": "Page",
				"page_name": "docs",
				"track_steps": 0,
				"save_on_complete": 0,
				"is_standard": 0,
				"steps": [
					{
						"ui_tour": 1,
						"title": "System Guide",
						"description": "Open the guide from any Desk screen.",
						"element_selector": "#huf-guide-launcher",
						"position": "Top",
					},
					{
						"ui_tour": 1,
						"title": "Search the guide",
						"description": "Enter a few words to find documentation you may read.",
						"element_selector": "#huf-guide-query",
						"position": "Bottom",
					},
					{
						"ui_tour": 1,
						"title": "Open source",
						"description": "Open the full article and check its steps before proceeding.",
						"element_selector": ".huf-guide-source",
						"position": "Top",
					},
				],
			}
		).insert()
	if not frappe.db.exists("HUF Guide Binding", "huf-guide-search"):
		frappe.get_doc(
			{
				"doctype": "HUF Guide Binding",
				"enabled": 1,
				"screen_type": "Page",
				"screen_name": "docs",
				"article_path": "guide/search",
				"form_tour": name,
				"priority": 10,
				"next_instruction": "Search the guide, open the source and follow its documented steps.",
				"target_type": "Page",
				"target_name": "docs",
			}
		).insert(set_name="huf-guide-search")
	return {"article": "guide/search", "tour": name}


def prepare():
	"""One explicit-site command; additive schema sync and missing defaults only."""
	frappe.only_for("System Manager")
	if not {"huf", "compendium"}.issubset(frappe.get_installed_apps()):
		frappe.throw(frappe._("Install HUF and compatible Compendium first."))
	from importlib.metadata import version

	if version("compendium").split(".")[0] != frappe.__version__.split(".")[0]:
		frappe.throw(frappe._("Install a compatible Compendium version before enabling the guide."))
	for name in ("huf_guide_settings", "huf_guide_binding"):
		frappe.reload_doc("huf", "doctype", name, force=True)
	for field, value in {
		"default_language": "user",
		"allow_translation_fallback": 1,
		"fallback_language": "en",
		"record_checks_enabled": 0,
	}.items():
		# Check Singles row existence: Frappe converts absent Check values to0,
		# which must not be confused with a deliberately saved disabled setting.
		if not frappe.db.sql(
			"select value from tabSingles where doctype=%s and field=%s", ("HUF Guide Settings", field)
		):
			frappe.db.set_single_value("HUF Guide Settings", field, value)
	seed_example()
	binding = frappe.get_doc("HUF Guide Binding", "huf-guide-search")
	if binding.article_path == "guide/search" and not binding.next_instruction:
		binding.next_instruction = "Search the guide, open the source and follow its documented steps."
		binding.save()
	return {
		"site": frappe.local.site,
		"mode": frappe.db.get_single_value("HUF Guide Settings", "mode"),
		"settings_preserved": True,
	}
