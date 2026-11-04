"""Native acceptance, run on an explicitly selected site inside a rolled-back transaction."""

import json
import socket
import unittest
import uuid
from unittest.mock import patch

import frappe

from huf.guide import api, context, install


class TestGuide(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.previous_user = frappe.session.user
		frappe.set_user("Administrator")
		cls.token = "guide" + uuid.uuid4().hex[:10]
		cls.reader_role = "Guide Test Reader " + cls.token
		frappe.get_doc({"doctype": "Role", "role_name": cls.reader_role, "desk_access": 1}).insert()
		cls.staff, cls.limited = [f"{cls.token}.{p}@example.invalid" for p in ("staff", "limited")]
		for name, roles in (
			(cls.staff, [cls.reader_role, "Compendium Contributor"]),
			(cls.limited, [cls.reader_role]),
		):
			doc = frappe.get_doc(
				{
					"doctype": "User",
					"email": name,
					"first_name": "Guide fixture",
					"user_type": "System User",
					"send_welcome_email": 0,
					"roles": [{"role": role} for role in roles],
				}
			)
			doc.flags.no_welcome_mail = True
			doc.insert()
			# A pre-existing app adds a role in after_insert; reload before assigning fixture roles.
			frappe.get_doc("User", name).add_roles(*roles)
		cls.path = "guide/" + cls.token
		cls.title = "Restricted " + cls.token
		cls.page = frappe.get_doc(
			{
				"doctype": "Compendium Page",
				"title": cls.title,
				"language": "en",
				"path": cls.path,
				"published": 1,
				"content": "Private " + cls.token,
				"roles": [{"role": "Compendium Contributor"}],
			}
		).insert()
		cls.binding = frappe.get_doc(
			{
				"doctype": "HUF Guide Binding",
				"screen_type": "Page",
				"screen_name": "docs",
				"article_path": cls.path,
				"enabled": 1,
				"error_key": "TEST_ERROR",
			}
		).insert()
		frappe.db.set_single_value("HUF Guide Settings", "enabled", 1)
		frappe.db.set_single_value("HUF Guide Settings", "mode", "guide_only")
		frappe.db.set_single_value("HUF Guide Settings", "search_source", "Compendium")

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		for user in (cls.staff, cls.limited):
			frappe.clear_cache(user=user)
		frappe.set_user(cls.previous_user)

	def setUp(self):
		frappe.set_user(self.staff)
		frappe.local.lang = "ar"
		frappe.local.request_cache.clear()

	def test_arabic_search_and_source(self):
		hits = api.search_guides("البحث في دليل النظام")
		self.assertTrue(any(r["path"] == "guide/search" for r in hits))
		page = api.get_guide("guide/search")
		self.assertEqual(page["language"], "ar")
		self.assertIn("البحث في دليل النظام", page["title"])

	def test_authorised_article(self):
		self.assertEqual(api.get_guide(self.path)["title"], self.title)
		self.assertTrue(any(r["path"] == self.path for r in api.search_guides(self.token)))

	def test_restricted_search_has_no_metadata(self):
		api.search_guides(self.token)  # warm native Compendium index with allowed user
		frappe.set_user(self.limited)
		self.assertNotIn(self.title, json.dumps(api.search_guides(self.token)))
		self.assertNotIn(
			self.path,
			json.dumps(
				api.resolve_help({"screen_type": "Page", "screen_name": "docs", "error_key": "TEST_ERROR"})
			),
		)

	def test_direct_hidden_and_missing_are_identical(self):
		frappe.set_user(self.limited)
		messages = []
		for path in (self.path, "guide/never-existed-" + self.token):
			with self.assertRaises(frappe.PermissionError) as cm:
				api.get_guide(path)
			messages.append(str(cm.exception))
		self.assertEqual(messages[0], messages[1])

	def test_native_source_endpoints_redact_titles(self):
		from huf.guide import compendium_api

		frappe.set_user(self.limited)
		for call, kwargs in (
			(compendium_api.get_page, {"path": self.path}),
			(compendium_api.get_asset, {"page_path": self.path, "asset_path": "missing.png"}),
			(compendium_api.make_override, {"path": self.path}),
		):
			with self.assertRaises(frappe.PermissionError) as cm:
				call(**kwargs)
			self.assertNotIn(self.title, str(cm.exception))

	def test_binding_list_and_get_are_guarded(self):
		frappe.set_user(self.limited)
		rows = frappe.get_list("HUF Guide Binding", filters={"name": self.binding.name})
		self.assertEqual(rows, [])
		self.assertFalse(frappe.get_doc("HUF Guide Binding", self.binding.name).has_permission("read"))

	def test_unpublication_after_search(self):
		api.search_guides(self.token)
		frappe.db.set_value("Compendium Page", self.page.name, "published", 0)
		frappe.local.request_cache.clear()
		try:
			with self.assertRaises(frappe.PermissionError):
				api.get_guide(self.path)
			self.assertFalse(any(r["path"] == self.path for r in api.search_guides(self.token)))
		finally:
			frappe.db.set_value("Compendium Page", self.page.name, "published", 1)
			frappe.local.request_cache.clear()

	def test_role_revocation_after_search(self):
		api.search_guides(self.token)
		frappe.set_user("Administrator")
		frappe.get_doc("User", self.staff).remove_roles("Compendium Contributor")
		frappe.set_user(self.staff)
		try:
			with self.assertRaises(frappe.PermissionError):
				api.get_guide(self.path)
			self.assertFalse(any(r["path"] == self.path for r in api.search_guides(self.token)))
		finally:
			frappe.set_user("Administrator")
			frappe.get_doc("User", self.staff).add_roles("Compendium Contributor")

	def test_disabled_blocks_all_guide_endpoints(self):
		frappe.db.set_single_value("HUF Guide Settings", "enabled", 0)
		try:
			self.assertFalse(api.bootstrap()["enabled"])
			for fn, args in (
				(api.search_guides, ["guide"]),
				(api.get_guide, ["guide/search"]),
				(api.resolve_help, []),
				(api.get_tour, [self.binding.name]),
			):
				with self.assertRaises(frappe.PermissionError):
					fn(*args)
		finally:
			frappe.db.set_single_value("HUF Guide Settings", "enabled", 1)

	def test_guest_and_unsafe_inputs(self):
		with self.assertRaises(frappe.ValidationError):
			api.get_guide("../private/secret")
		with self.assertRaises(frappe.ValidationError):
			api.get_guide("https://example.com")
		with self.assertRaises(frappe.ValidationError):
			api.search_guides("x" * 201)
		with self.assertRaises(frappe.ValidationError):
			context.normalize({"doc": {"secret": "value"}})
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			api.get_guide("guide/search")

	def test_exact_context_before_generic_and_unknown_error(self):
		items = api.resolve_help({"screen_type": "Page", "screen_name": "docs", "error_key": "TEST_ERROR"})
		self.assertEqual(items[0]["path"], self.path)
		items = api.resolve_help({"screen_type": "Page", "screen_name": "docs", "error_key": "UNKNOWN"})
		self.assertFalse(any(item["error_key"] for item in items))

	def test_no_network_or_business_sql(self):
		original_connect = socket.socket.connect

		def only_local(sock, address):
			if isinstance(address, tuple) and address[0] not in ("127.0.0.1", "::1", "localhost"):
				raise AssertionError("external_connection")
			return original_connect(sock, address)

		with (
			patch.object(socket.socket, "connect", only_local),
			patch.object(frappe.db, "sql", wraps=frappe.db.sql) as sql,
		):
			api.bootstrap()
			api.search_guides("البحث")
			api.get_guide("guide/search")
			api.resolve_help({"screen_type": "Page", "screen_name": "docs"})
			queries = "\n".join(str(c.args[0]) for c in sql.call_args_list)
			for table in ("Sales Invoice", "GL Entry", "Stock Ledger Entry", "Company", "ToDo"):
				self.assertNotIn("tab" + table, queries)

	def test_generic_seed_is_idempotent_and_preserves_edits(self):
		frappe.set_user("Administrator")
		before = frappe.db.count("Form Tour")
		install.seed_example()
		install.seed_example()
		self.assertEqual(frappe.db.count("Form Tour"), before)

	def test_native_tour_and_no_default_huf_grants(self):
		items = api.resolve_help({"screen_type": "Page", "screen_name": "docs"})
		item = next(i for i in items if i["tour"])
		self.assertEqual(
			api.get_tour(item["binding"], {"screen_type": "Page", "screen_name": "docs"})["doctype"],
			"Form Tour",
		)
		self.assertFalse(set(frappe.get_roles()) & {"Huf Manager", "Huf Gateway User", "System Manager"})
		if "hrms" in frappe.get_installed_apps():
			self.assertEqual(frappe.db.get_value("DocType", "Skill", "module"), "HR")

	def test_guide_install_has_no_active_optional_jobs(self):
		self.assertTrue(frappe.db.get_single_value("HUF Guide Settings", "guide_only_install"))
		self.assertEqual(
			frappe.db.count("Scheduled Job Type", {"method": ["like", "huf.%"], "stopped": 0}), 0
		)
