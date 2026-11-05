"""Private staging never grants roles or exposes navigation. No site writes."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from huf import deployment, permissions
from huf.huf.doctype.huf_user_role import huf_user_role
from huf.ai.agent import access


class TestStagedDeployment(unittest.TestCase):
	def test_upstream_defaults_remain_unchanged_without_site_flags(self):
		with patch.object(deployment, "frappe", SimpleNamespace(conf={})):
			self.assertTrue(deployment.automatic_roles_enabled())
			self.assertFalse(deployment.navigation_hidden())

	def test_opt_out_blocks_both_default_role_paths_before_any_user_read_or_write(self):
		with patch.object(deployment, "frappe", SimpleNamespace(conf={"huf_auto_assign_roles": 0})):
			self.assertFalse(huf_user_role.ensure_default_huf_roles("user@example.invalid"))
			self.assertEqual(huf_user_role.grant_default_roles_to_system_users(), 0)

	def test_hidden_tile_is_not_shown_even_to_administrators(self):
		with patch.object(deployment, "frappe", SimpleNamespace(conf={"huf_hidden": 1})):
			self.assertFalse(permissions.check_app_permission())

	def test_navigation_and_background_policy_are_scoped_to_huf(self):
		writes = []
		def rows(dt, filters=None, **kwargs):
			if dt == "Scheduled Job Type":
				self.assertEqual(filters, {"method": ["like", "huf.%"]})
				return ["huf-job"]
			self.assertIn(filters, [{"app": "huf"}, {"link_to": "Huf"}])
			return ["huf-icon"]
		fake = SimpleNamespace(conf={"huf_hidden": 1, "huf_background_enabled": 0}, get_all=rows,
			db=SimpleNamespace(exists=lambda *a: True, set_value=lambda *a, **k: writes.append((a, k))))
		with patch.object(deployment, "frappe", fake):
			deployment.apply_site_policy()
		self.assertIn((("Scheduled Job Type", "huf-job", "stopped", 1), {"update_modified": False}), writes)
		self.assertIn((("Workspace", "Huf", "is_hidden", 1), {"update_modified": False}), writes)
		self.assertEqual(len(writes), 4)

	def test_private_ui_denies_regular_users(self):
		def deny(message, error):
			raise error(message)
		fake = SimpleNamespace(conf={"huf_hidden": 1}, session=SimpleNamespace(user="regular@example.invalid"),
			get_roles=lambda: [], throw=deny, _=lambda s: s, PermissionError=frappe.PermissionError)
		with patch.object(deployment, "frappe", fake):
			with self.assertRaises(frappe.PermissionError):
				deployment.assert_private_ui_access()
			fake.session.user = "Administrator"
			deployment.assert_private_ui_access()

	def test_execution_switch_blocks_even_owner_before_provider_or_permission_work(self):
		with patch.object(access, "frappe", SimpleNamespace(conf={"huf_execution_enabled": 0})):
			self.assertFalse(access.check_agent_access(SimpleNamespace(owner="Administrator"), "Administrator"))
