import unittest
from unittest.mock import patch

import frappe

from huf.guide import api, install
from huf.guide.tests.test_guide import TestGuide


class TestGuideUX(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		TestGuide.setUpClass.__func__(cls)
		frappe.set_user("Administrator")
		cls.service = frappe.get_doc(
			{
				"doctype": "HUF Guide Binding",
				"screen_type": "Form",
				"screen_name": "Compendium Page",
				"article_path": "guide/search",
				"next_instruction": "Synthetic approved instruction",
				"target_type": "Form",
				"target_name": "Compendium Page",
				"target_field": "title",
				"record_check_enabled": 1,
				"record_check": "native_required_fields",
				"check_roles": [{"role": cls.reader_role}],
				"check_fields": "title",
				"complete_instruction": "Specified fields present",
				"incomplete_instruction": "Fill the mandatory title",
			}
		).insert()
		cls.screen = {"screen_type": "Form", "screen_name": "Compendium Page"}

	@classmethod
	def tearDownClass(cls):
		TestGuide.tearDownClass.__func__(cls)

	def setUp(self):
		frappe.db.savepoint("guide_ux")
		frappe.set_user(self.staff)
		frappe.local.lang = "ar"
		frappe.local.request_cache.clear()

	def tearDown(self):
		frappe.db.rollback(save_point="guide_ux")
		frappe.local.request_cache.clear()
		frappe.clear_document_cache("HUF Guide Settings", "HUF Guide Settings")

	def enable(self):
		frappe.db.set_single_value("HUF Guide Settings", "record_checks_enabled", 1)

	def check(self):
		return api.check_record(self.service.name, self.page.name, self.screen)

	def test_default_no_record_read(self):
		frappe.db.set_single_value("HUF Guide Settings", "record_checks_enabled", 0)
		with patch.object(frappe, "get_doc", wraps=frappe.get_doc) as calls:
			with self.assertRaises(frappe.PermissionError):
				self.check()
			self.assertFalse(
				any(c.args[:2] == ("Compendium Page", self.page.name) for c in calls.call_args_list)
			)

	def test_documented_step_does_not_read_record(self):
		with patch.object(frappe, "get_doc", wraps=frappe.get_doc) as calls:
			item = next(i for i in api.resolve_help(self.screen) if i["binding"] == self.service.name)
			self.assertEqual(item["instruction"], "Synthetic approved instruction")
			self.assertEqual(item["action"]["field"], "title")
			self.assertFalse(
				any(c.args[:2] == ("Compendium Page", self.page.name) for c in calls.call_args_list)
			)

	def test_complete_and_incomplete_saved_fields(self):
		self.enable()
		before = frappe.db.count("Compendium Page")
		self.assertEqual(self.check()["state"], "complete")
		frappe.db.set_value("Compendium Page", self.page.name, "title", "")
		result = self.check()
		self.assertEqual(result["state"], "incomplete")
		self.assertEqual(result["instruction"], "Fill the mandatory title")
		self.assertNotIn(self.token, frappe.as_json(result))
		self.assertEqual(frappe.db.count("Compendium Page"), before)
		self.assertEqual(frappe.db.get_value("Compendium Page", self.page.name, "title"), "")

	def test_limited_document_permission_and_guessed_name(self):
		self.enable()
		frappe.set_user(self.limited)
		with self.assertRaises(frappe.PermissionError):
			self.check()
		frappe.set_user(self.staff)
		with self.assertRaises(frappe.PermissionError):
			api.check_record(self.service.name, "nonexistent", self.screen)

	def test_service_role_and_service_toggle(self):
		self.enable()
		frappe.db.set_value("HUF Guide Binding", self.service.name, "record_check_enabled", 0)
		with self.assertRaises(frappe.PermissionError):
			self.check()
		frappe.db.set_value("HUF Guide Binding", self.service.name, "record_check_enabled", 1)
		frappe.db.delete("Has Role", {"parent": self.service.name, "parenttype": "HUF Guide Binding"})
		with self.assertRaises(frappe.PermissionError):
			self.check()

	def test_no_script_or_undeclared_check(self):
		self.enable()
		frappe.db.set_value("HUF Guide Binding", self.service.name, "record_check", "os.system")
		with self.assertRaises(frappe.ValidationError):
			self.check()

	def test_native_check_rejects_nonmandatory_fields(self):
		self.enable()
		frappe.db.set_value("HUF Guide Binding", self.service.name, "check_fields", "content")
		with self.assertRaises(frappe.ValidationError):
			self.check()

	def test_missing_destination_not_returned(self):
		frappe.db.set_value("HUF Guide Binding", self.service.name, "target_field", "no_such_field")
		item = next(i for i in api.resolve_help(self.screen) if i["binding"] == self.service.name)
		self.assertIsNone(item["action"])

	def test_roles_exclusion_wins(self):
		frappe.set_user("Administrator")
		settings = frappe.get_single("HUF Guide Settings")
		settings.append("allowed_roles", {"role": self.reader_role})
		settings.append("denied_roles", {"role": self.reader_role})
		settings.save()
		frappe.set_user(self.staff)
		self.assertFalse(api.bootstrap(self.screen)["enabled"])
		with self.assertRaises(frappe.PermissionError):
			api.get_guide("guide/search", self.screen)

	def test_screen_exclusion_wins(self):
		frappe.db.set_single_value(
			"HUF Guide Settings",
			{"included_screens": "Form:Compendium Page", "excluded_screens": "Form:Compendium Page"},
		)
		self.assertFalse(api.bootstrap(self.screen)["enabled"])
		with self.assertRaises(frappe.PermissionError):
			api.resolve_help(self.screen)

	def test_readiness_manager_only_and_fixes(self):
		with self.assertRaises(frappe.PermissionError):
			api.readiness()
		frappe.set_user("Administrator")
		frappe.db.set_value("HUF Guide Binding", self.service.name, "article_path", "guide/not-published")
		item = next(i for i in api.readiness()["services"] if i["binding"] == self.service.name)
		self.assertFalse(item["ready"])
		self.assertTrue(item["issues"])

	def test_prepare_is_idempotent_preserves_settings(self):
		# Schema sync is tested separately outside rollback (DDL is not transactional).
		frappe.set_user("Administrator")
		frappe.db.set_single_value("HUF Guide Settings", "support_channel", "Synthetic support")
		install.seed_example()
		install.seed_example()
		self.assertEqual(
			frappe.db.get_single_value("HUF Guide Settings", "support_channel"), "Synthetic support"
		)

	def test_no_documented_result_does_not_guess_action(self):
		self.enable()
		frappe.db.set_value("HUF Guide Binding", self.service.name, "complete_instruction", "")
		result = self.check()
		self.assertEqual(result["state"], "unknown")
		self.assertIsNone(result["action"])

	def test_native_row_scope_and_no_side_effect(self):
		self.enable()
		frappe.set_user("Administrator")
		own = frappe.get_doc(
			{"doctype": "ToDo", "description": "Synthetic required-field check", "allocated_to": self.staff}
		).insert()
		other = frappe.get_doc(
			{"doctype": "ToDo", "description": "Synthetic outside scope", "allocated_to": self.limited}
		).insert()
		binding = frappe.get_doc(
			{
				"doctype": "HUF Guide Binding",
				"screen_type": "Form",
				"screen_name": "ToDo",
				"article_path": "guide/search",
				"record_check_enabled": 1,
				"record_check": "native_required_fields",
				"check_roles": [{"role": self.reader_role}],
				"check_fields": "description",
				"complete_instruction": "Specified fields present",
			}
		).insert()
		frappe.set_user(self.staff)
		screen = {"screen_type": "Form", "screen_name": "ToDo"}
		before = frappe.db.get_value("ToDo", own.name, "modified")
		self.assertEqual(api.check_record(binding.name, own.name, screen)["state"], "complete")
		with self.assertRaises(frappe.PermissionError):
			api.check_record(binding.name, other.name, screen)
		self.assertEqual(frappe.db.get_value("ToDo", own.name, "modified"), before)
