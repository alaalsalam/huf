import frappe
from frappe import _

SETTINGS = "HUF Guide Settings"


def guide_installation():
	"""Site-local installation profile; never cached across sites or users."""
	return (
		bool(frappe.db.get_single_value(SETTINGS, "guide_only_install"))
		if frappe.db.exists("DocType", SETTINGS)
		else False
	)


def require_access():
	if frappe.session.user == "Guest" or "Desk User" not in frappe.get_roles():
		frappe.throw(_("System Guide is unavailable."), frappe.PermissionError)
	settings = frappe.get_single(SETTINGS)
	if not settings.enabled or settings.mode != "guide_only":
		frappe.throw(_("System Guide is unavailable."), frappe.PermissionError)
	return settings


def ai_adapter():
	"""Future integration belongs to huf.ai.agent.chat; no second chat engine."""
	require_access()
	frappe.throw(_("AI guidance is not enabled."), frappe.PermissionError)
