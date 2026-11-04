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


def screen_rules(value):
	return {line.strip() for line in (value or "").splitlines() if line.strip()}


def roles_allowed(allowed, denied=()):
	roles = set(frappe.get_roles())
	return not (roles & {r.role for r in denied}) and (not allowed or bool(roles & {r.role for r in allowed}))


def screen_permitted(settings, context):
	include, exclude = screen_rules(settings.included_screens), screen_rules(settings.excluded_screens)
	key = f"{context.get('screen_type')}:{context.get('screen_name')}"
	return key not in exclude and (not include or key in include)


def require_access(context=None):
	if frappe.session.user == "Guest" or "Desk User" not in frappe.get_roles():
		frappe.throw(_("System Guide is unavailable."), frappe.PermissionError)
	settings = frappe.get_single(SETTINGS)
	if not settings.enabled or settings.mode != "guide_only":
		frappe.throw(_("System Guide is unavailable."), frappe.PermissionError)
	if not roles_allowed(settings.allowed_roles, settings.denied_roles) or not screen_permitted(
		settings, context or {}
	):
		frappe.throw(_("System Guide is unavailable."), frappe.PermissionError)
	return settings


def ai_adapter():
	"""Future integration belongs to huf.ai.agent.chat; no second chat engine."""
	require_access()
	frappe.throw(_("AI guidance is not enabled."), frappe.PermissionError)
