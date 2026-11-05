"""Site-scoped controls for a staged, private HUF installation.

These flags never change other sites, existing user assignments or provider secrets.
Absent flags retain upstream behaviour.
"""
import frappe


def automatic_roles_enabled():
	return bool(frappe.conf.get("huf_auto_assign_roles", True))


def navigation_hidden():
	return bool(frappe.conf.get("huf_hidden", False))


def apply_site_policy():
	"""Reapply after migration; only HUF-owned navigation/jobs are affected."""
	if navigation_hidden():
		if frappe.db.exists("DocType", "Desktop Icon"):
			for name in frappe.get_all("Desktop Icon", filters={"app": "huf"}, pluck="name"):
				frappe.db.set_value("Desktop Icon", name, "hidden", 1, update_modified=False)
			for name in frappe.get_all("Desktop Icon", filters={"link_to": "Huf"}, pluck="name"):
				frappe.db.set_value("Desktop Icon", name, "hidden", 1, update_modified=False)
		if frappe.db.exists("Workspace", "Huf"):
			frappe.db.set_value("Workspace", "Huf", "is_hidden", 1, update_modified=False)
	if not frappe.conf.get("huf_background_enabled", True):
		for name in frappe.get_all("Scheduled Job Type", filters={"method": ["like", "huf.%"]}, pluck="name"):
			frappe.db.set_value("Scheduled Job Type", name, "stopped", 1, update_modified=False)


def assert_private_ui_access():
	if navigation_hidden() and frappe.session.user != "Administrator" and "System Manager" not in frappe.get_roles():
		frappe.throw(frappe._("HUF is being prepared and is available to system administrators only."), frappe.PermissionError)
