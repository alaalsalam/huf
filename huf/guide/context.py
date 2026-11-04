import frappe
from frappe import _

from huf.guide import knowledge

SCREEN_TYPES = ("Page", "Form", "List", "Workspace")


def normalize(context):
	data = frappe.parse_json(context) if isinstance(context, str) else context
	if data is None:
		return {}
	if not isinstance(data, dict) or set(data) - {"screen_type", "screen_name", "fieldname", "error_key"}:
		frappe.throw(_("Invalid guide context."), frappe.ValidationError)
	if any(not isinstance(v, str) or len(v) > 140 for v in data.values()):
		frappe.throw(_("Invalid guide context."), frappe.ValidationError)
	if data.get("screen_type") not in SCREEN_TYPES or not data.get("screen_name"):
		return {}
	return data


def screen_allowed(context):
	kind, name = context.get("screen_type"), context.get("screen_name")
	if kind in ("Form", "List"):
		return frappe.db.exists("DocType", name) and frappe.has_permission(name, "read")
	if kind == "Page":
		if not frappe.db.exists("Page", name):
			return False
		return frappe.get_doc("Page", name).is_permitted()
	if kind == "Workspace":
		if not frappe.db.exists("Workspace", name):
			return False
		workspace = frappe.get_doc("Workspace", name)
		roles = {r.role for r in workspace.roles}
		return workspace.has_permission("read") and (not roles or bool(roles & set(frappe.get_roles())))
	return False


def resolve(context):
	context = normalize(context)
	if not screen_allowed(context):
		return []
	rows = frappe.get_list(
		"HUF Guide Binding",
		filters={"enabled": 1, "screen_type": context["screen_type"], "screen_name": context["screen_name"]},
		fields=["name", "fieldname", "error_key", "priority"],
		limit_page_length=100,
	)
	rows = [r for r in rows if all(not r[k] or r[k] == context.get(k) for k in ("fieldname", "error_key"))]
	rows.sort(key=lambda r: (-bool(r.error_key), -bool(r.fieldname), -(r.priority or 0), r.name))
	results = []
	for row in rows:
		binding = frappe.get_doc("HUF Guide Binding", row.name)
		if not binding.has_permission("read"):
			continue
		try:
			page = knowledge.read(binding.article_path)
		except frappe.PermissionError:
			continue
		item = {key: page[key] for key in ("path", "title", "url", "language")}
		item["binding"] = binding.name
		item["error_key"] = binding.error_key or ""
		item["tour"] = permitted_tour(binding)
		results.append(item)
	return results


def permitted_tour(binding):
	if not binding.form_tour or not frappe.has_permission("Form Tour", "read", binding.form_tour):
		return None
	tour = frappe.get_doc("Form Tour", binding.form_tour)
	if tour.save_on_complete or any(step.next_form_tour or step.next_step_condition for step in tour.steps):
		return None
	return binding.form_tour
