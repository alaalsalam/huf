import frappe

from huf.guide import context, knowledge


def binding_allowed(doc, user=None, ptype="read", **kwargs):
	if ptype not in (None, "read", "select"):
		return True
	if user and user != frappe.session.user:
		return False
	if "System Manager" in frappe.get_roles():
		return True
	if not context.screen_allowed({"screen_type": doc.screen_type, "screen_name": doc.screen_name}):
		return False
	try:
		knowledge.read(doc.article_path)
	except (frappe.PermissionError, frappe.ValidationError):
		return False
	return True  # Frappe still checks the ordinary DocType / User Permission ceiling.


def binding_query(user=None):
	if user and user != frappe.session.user:
		return "1=0"
	if "System Manager" in frappe.get_roles():
		return ""
	allowed = []
	# Internal configuration scan only; native permission checks run on every candidate.
	for row in frappe.get_all(
		"HUF Guide Binding", fields=["name", "screen_type", "screen_name", "article_path"]
	):
		if binding_allowed(row) is not False:
			allowed.append(frappe.db.escape(row.name))
	return "`tabHUF Guide Binding`.`name` in (" + ",".join(allowed) + ")" if allowed else "1=0"
