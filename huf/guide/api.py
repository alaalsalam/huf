import frappe

from huf.guide import context as guide_context
from huf.guide import knowledge, policy


@frappe.whitelist()
def bootstrap():
	try:
		settings = policy.require_access()
	except frappe.PermissionError:
		return {"enabled": False}
	return {
		"enabled": True,
		"mode": "guide_only",
		"api_revision": "system-guide-v1",
		"support": settings.support_channel or "",
	}


@frappe.whitelist()
def search_guides(query, context=None):
	policy.require_access()
	guide_context.normalize(context)
	return knowledge.find(query)


@frappe.whitelist()
def get_guide(path):
	policy.require_access()
	return knowledge.read(path)


@frappe.whitelist()
def resolve_help(context=None):
	policy.require_access()
	return guide_context.resolve(context)


@frappe.whitelist()
def get_tour(binding, context=None):
	policy.require_access()
	for item in guide_context.resolve(context):
		if item["binding"] == binding and item["tour"]:
			doc = frappe.get_doc("Form Tour", item["tour"])
			doc.check_permission("read")
			return doc.as_dict()
	frappe.throw(frappe._("Guide unavailable or not permitted."), frappe.PermissionError)
