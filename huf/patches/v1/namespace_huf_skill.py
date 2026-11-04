"""Preserve legacy HUF skill records without ever renaming HRMS's Skill."""

import frappe


def execute():
	if frappe.db.get_value("DocType", "Skill", "module") != "Huf":
		return
	if frappe.db.exists("DocType", "HUF Skill"):
		frappe.throw("Both legacy and namespaced HUF skill definitions exist; review before migration.")
	frappe.rename_doc("DocType", "Skill", "HUF Skill")
