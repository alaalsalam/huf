import re
from urllib.parse import quote

import frappe
from compendium import docs, search
from frappe import _


def logical_path(path):
	if not isinstance(path, str) or len(path) > 240 or not re.fullmatch(r"[\w/-]+", path):
		frappe.throw(_("Invalid guide reference."), frappe.ValidationError)
	if any(part in ("", ".", "..") for part in path.split("/")):
		frappe.throw(_("Invalid guide reference."), frappe.ValidationError)
	return path


def read(path):
	path = logical_path(path)
	settings = frappe.get_single("HUF Guide Settings")
	locale = (
		frappe.local.lang if settings.default_language in (None, "", "user") else settings.default_language
	)
	try:
		# Compendium owns discovery, publication, canonical-language ACL and rendering.
		page = docs.get_page(path=path, locale=locale)
		if page["is_fallback"]:
			if not settings.allow_translation_fallback:
				frappe.throw(_("Guide unavailable or not permitted."), frappe.PermissionError)
			page = docs.get_page(path=path, locale=settings.fallback_language or "en")
	except (frappe.PermissionError, frappe.DoesNotExistError):
		# Neither titles nor different error messages disclose a hidden page's existence.
		raise frappe.PermissionError(_("Guide unavailable or not permitted.")) from None
	return {
		"path": page["path"],
		"title": page["title"],
		"content": page["content"],
		"language": page["language"],
		"is_fallback": page["is_fallback"],
		"url": f"/desk/docs/{quote(page['locale'], safe='')}/{quote(page['path'], safe='/')}",
	}


def find(query):
	if not isinstance(query, str) or len(query) > 200:
		frappe.throw(_("Enter up to 200 characters."), frappe.ValidationError)
	match = search.build_match_query(query)
	if not match:
		return []
	results = []
	settings = frappe.get_single("HUF Guide Settings")
	locale = (
		frappe.local.lang if settings.default_language in (None, "", "user") else settings.default_language
	)
	for path, _title, snippet in search.search(docs.normalize_locale(locale), match):
		try:
			# Recheck current publication and roles even when the native search index is warm.
			page = read(path)
		except frappe.PermissionError:
			continue
		results.append(
			{key: page[key] for key in ("path", "title", "url", "language")} | {"snippet": snippet}
		)
	return results
