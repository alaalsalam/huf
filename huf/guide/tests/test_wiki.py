"""Native Wiki permission/publication checks; synthetic rows always roll back."""

import json
import unittest
from unittest.mock import patch

import frappe

from huf.guide import api
from huf.guide.tests.test_guide import TestGuide


class TestGuideWiki(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		TestGuide.setUpClass.__func__(cls)
		frappe.set_user("Administrator")
		cls.route = "guide-wiki-" + cls.token
		cls.space = frappe.get_doc(
			{
				"doctype": "Wiki Space",
				"space_name": cls.route,
				"route": cls.route,
				"is_published": 1,
				"roles": [{"role": "Compendium Contributor", "permission_level": "Read"}],
			}
		).insert()
		cls.wiki_page = frappe.get_doc(
			{
				"doctype": "Wiki Document",
				"title": "عنوان حالي " + cls.token,
				"route": cls.route + "/help",
				"slug": "help",
				"wiki_space": cls.space.name,
				"parent_wiki_document": cls.space.root_group,
				"is_published": 1,
				"content": "# عنوان حالي\n\nشرح حديث للموظف " + cls.token + "<script>alert(1)</script>",
			}
		).insert()
		frappe.db.set_single_value("HUF Guide Settings", "search_source", "Wiki")
		frappe.db.set_single_value("HUF Guide Settings", "wiki_spaces", cls.route)
		cls.ref = "wiki:" + cls.wiki_page.route

	@classmethod
	def tearDownClass(cls):
		TestGuide.tearDownClass.__func__(cls)

	def setUp(self):
		frappe.db.savepoint("guide_wiki")
		frappe.set_user(self.staff)
		frappe.local.request_cache.clear()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point="guide_wiki")
		frappe.clear_document_cache("Wiki Space", self.space.name)
		frappe.local.request_cache.clear()

	def indexed(self):
		from wiki.frappe_wiki.doctype.wiki_document.wiki_sqlite_search import WikiSQLiteSearch

		return patch.object(
			WikiSQLiteSearch,
			"search",
			return_value={
				"results": [
					{
						"route": self.wiki_page.route,
						"title": "Stale indexed title",
						"content": "Stale indexed secret",
					}
				]
			},
		)

	def test_authorised_live_source_and_sanitized_body(self):
		page = api.get_guide(self.ref)
		self.assertEqual(page["url"], "/" + self.wiki_page.route)
		self.assertEqual(page["source"], "Wiki")
		self.assertIn("شرح حديث", page["content"])
		self.assertNotIn("<script", page["content"])

	def test_denied_read_and_search_have_no_title_or_snippet(self):
		frappe.set_user(self.limited)
		with self.indexed():
			self.assertEqual(api.search_guides(self.token), [])
		with self.assertRaises(frappe.PermissionError) as caught:
			api.get_guide(self.ref)
		self.assertNotIn(self.token, str(caught.exception))

	def test_current_acl_revocation_blocks_warm_results(self):
		api.get_guide(self.ref)
		frappe.set_user("Administrator")
		doc = frappe.get_doc("Wiki Space", self.space.name)
		doc.set("roles", [{"role": "System Manager", "permission_level": "Read"}])
		doc.save()
		frappe.set_user(self.staff)
		with self.indexed():
			self.assertEqual(api.search_guides(self.token), [])
		with self.assertRaises(frappe.PermissionError):
			api.get_guide(self.ref)

	def test_unpublished_page_denied(self):
		frappe.db.set_value("Wiki Document", self.wiki_page.name, "is_published", 0)
		with self.indexed():
			self.assertEqual(api.search_guides(self.token), [])
		with self.assertRaises(frappe.PermissionError):
			api.get_guide(self.ref)

	def test_unpublished_space_denied(self):
		frappe.db.set_value("Wiki Space", self.space.name, "is_published", 0)
		with self.assertRaises(frappe.PermissionError):
			api.get_guide(self.ref)

	def test_snippets_use_current_permitted_content_not_index(self):
		with self.indexed():
			result = api.search_guides(self.token)
		self.assertEqual(result[0]["title"], self.wiki_page.title)
		self.assertIn("شرح حديث", result[0]["snippet"])
		self.assertNotIn("Stale indexed", json.dumps(result))

	def test_unconfigured_spaces_and_external_paths_denied(self):
		frappe.db.set_single_value("HUF Guide Settings", "wiki_spaces", "")
		with self.assertRaises(frappe.PermissionError):
			api.get_guide(self.ref)
		for path in ("wiki:../etc/passwd", "wiki:https://example.invalid", "wiki:/help", "wiki:crms//help"):
			with self.assertRaises(frappe.ValidationError):
				api.get_guide(path)

	def test_compendium_reference_still_works_when_wiki_search_selected(self):
		self.assertEqual(api.get_guide(self.path)["source"], "Compendium")

	def test_wiki_only_import_does_not_require_compendium_read(self):
		with patch("compendium.docs.get_page", side_effect=AssertionError("Wrong source")):
			self.assertEqual(api.get_guide(self.ref)["source"], "Wiki")
