"""Read the installed Wiki's published manuals, never a second article store.

Wiki's website reader contract is space access + page/space publication. Desk
DocPerm on Wiki Document governs editors and is not substituted for that contract.
The configured space routes curate manuals; they never grant access to a space.
"""

import re
from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import sanitize_html, strip_html


def route_path(route):
	if (
		not isinstance(route, str)
		or len(route) > 500
		or not re.fullmatch(r"[\w/-]+", route)
		or any(part in ("", ".", "..") for part in route.split("/"))
	):
		frappe.throw(_("Invalid guide reference."), frappe.ValidationError)
	return route


def spaces():
	if "wiki" not in frappe.get_installed_apps():
		return []
	from wiki.permissions import can_read_space

	from huf.guide.policy import screen_rules

	routes = screen_rules(frappe.db.get_single_value("HUF Guide Settings", "wiki_spaces"))
	if not routes:
		return []
	return [
		row
		for row in frappe.get_all(
			"Wiki Space",
			filters={"route": ["in", sorted(routes)], "is_published": 1},
			fields=["name", "route", "root_group"],
		)
		if can_read_space(row.name)
	]


def read(route):
	route = route_path(route)
	allowed = {row.name for row in spaces()}
	name = frappe.db.get_value("Wiki Document", {"route": route}, "name") if allowed else None
	if not name:
		_deny()
	doc = frappe.get_doc("Wiki Document", name)  # Fresh content/publication on every read.
	if doc.wiki_space not in allowed or doc.is_group or doc.is_external_link:
		_deny()
	try:
		doc.check_space_access("read")
		doc.check_published()
	except (frappe.PermissionError, frappe.DoesNotExistError):
		_deny()
	from wiki.wiki.markdown import render_markdown

	return {
		"path": "wiki:" + doc.route,
		"title": doc.title,
		"content": sanitize_html(render_markdown(doc.content or ""), always_sanitize=True),
		"url": "/" + quote(doc.route, safe="/"),
		"source": "Wiki",
		"language": "",  # Wiki owns authored language; no inferred/automatic translation.
		"is_fallback": False,
	}


def find(query):
	from wiki.frappe_wiki.doctype.wiki_document.wiki_sqlite_search import WikiSQLiteSearch

	roots = [row.root_group for row in spaces() if row.root_group]
	if not query.strip() or not roots:
		return []
	search = WikiSQLiteSearch()
	if not search.index_exists():
		frappe.throw(_("Wiki search is not ready. Ask the site administrator to check its native index."))
	results = []
	for hit in search.search(query, filters={"space": roots})["results"]:
		try:
			page = read(hit["route"])
		except frappe.PermissionError:
			continue
		# Never emit cached indexed titles/snippets after an edit or ACL revocation.
		text = re.sub(r"\s+", " ", strip_html(page["content"]))
		tokens = re.findall(r"\w+", query.casefold())
		positions = [text.casefold().find(token) for token in tokens if token in text.casefold()]
		start = max(0, min(positions, default=0) - 65)
		results.append(
			{k: page[k] for k in ("path", "title", "url", "language", "source")}
			| {"snippet": ("…" if start else "") + text[start : start + 240]}
		)
		if len(results) >= 20:
			break
	return results


def _deny():
	frappe.throw(_("Guide unavailable or not permitted."), frappe.PermissionError)
