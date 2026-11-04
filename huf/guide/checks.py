"""Explicit read-only checks, never executable rules from settings.

Domain apps register huf_guide_record_checks = {key: definition_factory_path}.
A trusted factory returns doctype, fields and a callable run(values). It owns the
documented business rule. The only generic check uses native unconditional reqd.
"""

import re

import frappe
from frappe import _

from huf.guide import context, policy


def fields_for(binding):
	fields = [v.strip() for v in (binding.check_fields or "").splitlines() if v.strip()]
	if not fields or len(fields) > 20 or any(not re.fullmatch(r"[a-z][a-z0-9_]*", v) for v in fields):
		frappe.throw(_("Choose explicit fields for this check."))
	return list(dict.fromkeys(fields))


def definition(binding):
	fields = fields_for(binding)
	meta = frappe.get_meta(binding.screen_name)
	if meta.issingle or meta.istable or binding.screen_type != "Form":
		frappe.throw(_("Record checks require a saved form."))
	if binding.record_check == "native_required_fields":
		for name in fields:
			df = meta.get_field(name)
			if (
				not df
				or not df.reqd
				or df.mandatory_depends_on
				or df.fieldtype in ("Password", "Table", "Table MultiSelect")
			):
				frappe.throw(_("Choose unconditional native mandatory fields only."))
		return {"fields": fields, "run": required_fields}
	registered = frappe.get_hooks("huf_guide_record_checks") or {}
	paths = registered.get(binding.record_check, [])
	if isinstance(paths, str):
		paths = [paths]
	if len(paths) != 1:
		frappe.throw(_("The domain check is not registered."))
	spec = frappe.get_attr(paths[0])()
	if (
		spec.get("doctype") != binding.screen_name
		or set(spec.get("fields", [])) != set(fields)
		or not callable(spec.get("run"))
	):
		frappe.throw(_("The domain check does not match the allowed fields."))
	return spec


def required_fields(values):
	return {
		"state": "incomplete" if any(v is None or v == "" or v == [] for v in values.values()) else "complete"
	}


def run(binding_name, document_name, screen_context):
	settings = policy.require_access(screen_context)
	# Reject before touching any transaction document, including a guessed name.
	if not settings.record_checks_enabled:
		frappe.throw(_("Record checks are disabled."), frappe.PermissionError)
	items = context.resolve(screen_context)
	item = next((v for v in items if v["binding"] == binding_name and v["can_check"]), None)
	if not item:
		frappe.throw(_("Record check unavailable or not permitted."), frappe.PermissionError)
	binding = frappe.get_doc("HUF Guide Binding", binding_name)
	spec = definition(binding)
	if not isinstance(document_name, str) or not document_name or len(document_name) > 140:
		frappe.throw(_("Record checks require a saved form."))
	try:
		# Native document loading is required for full row/owner/User Permission/Core
		# hooks. Never substitute a partial document that could bypass those checks.
		doc = frappe.get_doc(binding.screen_name, document_name)
		doc.check_permission("read")
		for field in spec["fields"]:
			df = doc.meta.get_field(field)
			if (
				not df
				or df.fieldtype == "Password"
				or df.get("mask")
				or not doc.has_permlevel_access_to(field, permission_type="read")
			):
				frappe.throw(_("Record check unavailable or not permitted."), frappe.PermissionError)
		# Only the configured, readable projection reaches domain code or UI results.
		result = spec["run"]({field: doc.get(field) for field in spec["fields"]})
	except (frappe.DoesNotExistError, frappe.PermissionError):
		raise frappe.PermissionError(_("Record check unavailable or not permitted.")) from None
	state = result.get("state") if isinstance(result, dict) else "unknown"
	if state not in ("complete", "incomplete"):
		state = "unknown"
	instruction = (
		binding.complete_instruction
		if state == "complete"
		else binding.incomplete_instruction
		if state == "incomplete"
		else ""
	)
	if not instruction:
		state = "unknown"
	return {
		"kind": "record_check",
		"state": state,
		"instruction": instruction or _("No documented guidance is available for this situation."),
		"source": {k: item[k] for k in ("title", "path", "url")},
		"action": item["action"] if state != "unknown" else None,
		"limitation": _(
			"This checks the specified saved fields only, not completion of the business procedure."
		),
	}
