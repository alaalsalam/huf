"""Preserve native access decisions while suppressing denied-page title disclosure.

Compendium's native get_view and search already omit denied metadata. Its three
other reading endpoints include a denied title in PermissionError. Supported
Frappe method overrides redact that error without modifying Compendium source.
"""

import frappe
from compendium import docs
from frappe import _


def _read(call, **kwargs):
	try:
		return call(**kwargs)
	except (frappe.PermissionError, frappe.DoesNotExistError):
		raise frappe.PermissionError(_("Guide unavailable or not permitted.")) from None


@frappe.whitelist()
def get_page(path="", locale=None):
	return _read(docs.get_page, path=path, locale=locale)


@frappe.whitelist()
def get_asset(page_path, asset_path, locale=None):
	return _read(docs.get_asset, page_path=page_path, asset_path=asset_path, locale=locale)


@frappe.whitelist()
def make_override(path, locale=None):
	return _read(docs.make_override, path=path, locale=locale)
