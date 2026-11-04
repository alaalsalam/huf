import unittest
from unittest.mock import patch

from huf.patches.v1 import namespace_huf_skill


class TestSkillNamespace(unittest.TestCase):
	def test_foreign_skill_is_never_renamed(self):
		with (
			patch.object(namespace_huf_skill.frappe.db, "get_value", return_value="HR"),
			patch.object(namespace_huf_skill.frappe, "rename_doc") as rename,
		):
			namespace_huf_skill.execute()
			rename.assert_not_called()

	def test_only_legacy_huf_skill_is_renamed(self):
		with (
			patch.object(namespace_huf_skill.frappe.db, "get_value", return_value="Huf"),
			patch.object(namespace_huf_skill.frappe.db, "exists", return_value=False),
			patch.object(namespace_huf_skill.frappe, "rename_doc") as rename,
		):
			namespace_huf_skill.execute()
			rename.assert_called_once_with("DocType", "Skill", "HUF Skill")

	def test_ambiguous_existing_definitions_stop(self):
		with (
			patch.object(namespace_huf_skill.frappe.db, "get_value", return_value="Huf"),
			patch.object(namespace_huf_skill.frappe.db, "exists", return_value=True),
			patch.object(namespace_huf_skill.frappe, "rename_doc") as rename,
		):
			with self.assertRaises(namespace_huf_skill.frappe.ValidationError):
				namespace_huf_skill.execute()
			rename.assert_not_called()
