import frappe

from huf.guide import checks, knowledge, policy
from huf.guide import context as guide_context


@frappe.whitelist()
def bootstrap(context=None):
	try:
		settings = policy.require_access(guide_context.normalize(context))
	except frappe.PermissionError:
		return {"enabled": False}
	screen = guide_context.normalize(context)
	label = screen.get("screen_name") or "Current screen"
	if screen.get("screen_type") == "Page" and frappe.db.exists("Page", label):
		label = frappe.db.get_value("Page", label, "title") or label
	return {
		"enabled": True,
		"mode": "guide_only",
		"api_revision": "system-guide-ux-v2",
		"support": settings.support_channel or "",
		"screen_label": frappe._(label),
	}


@frappe.whitelist()
def search_guides(query, context=None):
	policy.require_access(guide_context.normalize(context))
	return knowledge.find(query)


@frappe.whitelist()
def get_guide(path, context=None):
	policy.require_access(guide_context.normalize(context))
	return knowledge.read(path)


@frappe.whitelist()
def resolve_help(context=None):
	policy.require_access(guide_context.normalize(context))
	return guide_context.resolve(context)


@frappe.whitelist()
def get_tour(binding, context=None):
	policy.require_access(guide_context.normalize(context))
	for item in guide_context.resolve(context):
		if item["binding"] == binding and item["tour"]:
			doc = frappe.get_doc("Form Tour", item["tour"])
			doc.check_permission("read")
			return doc.as_dict()
	frappe.throw(frappe._("Guide unavailable or not permitted."), frappe.PermissionError)


@frappe.whitelist()
def check_record(binding, document_name, context=None):
	return checks.run(binding, document_name, guide_context.normalize(context))


@frappe.whitelist()
def readiness():
	from huf.guide.readiness import inspect_services

	frappe.only_for("System Manager")
	return inspect_services()
