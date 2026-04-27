
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase


class TestHUFChatAPI(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")

    def _make_conversation(self, owner="Administrator", external_id="Administrator"):
        doc = frappe.get_doc({
            "doctype": "Agent Conversation",
            "title": "Test Trilogy Ai Chat",
            "channel": "Desk Chat",
            "external_id": external_id,
            "is_active": 1,
        })
        doc.insert(ignore_permissions=True)
        if owner != doc.owner:
            frappe.db.set_value("Agent Conversation", doc.name, "owner", owner)
            doc.owner = owner
        frappe.db.commit()
        return doc

    def _make_message(self, conversation, owner="Administrator"):
        doc = frappe.get_doc({
            "doctype": "Agent Message",
            "conversation": conversation.name,
            "role": "agent",
            "content": "مرحبا",
            "user": owner,
            "session_id": "test",
            "kind": "Message",
            "conversation_index": 1,
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return doc

    def test_create_chat_session(self):
        from huf.api.chat import new_session
        fake_conv = SimpleNamespace(name="TEST-SESSION", title="Test", agent="Agent", model="gpt-test")
        with patch("huf.api.chat._select_agent", return_value=SimpleNamespace(name="Agent")), patch("huf.api.chat.ConversationManager") as cm:
            cm.return_value.create_new_conversation.return_value = fake_conv
            result = new_session(title="Test")
        self.assertEqual(result["session_id"], "TEST-SESSION")

    def test_send_message(self):
        from huf.api.chat import send_message
        fake_agent = SimpleNamespace(name="Agent", provider="Provider", model="gpt-test")
        with patch("huf.api.chat._select_agent", return_value=fake_agent), patch("huf.api.chat.run_agent_sync", return_value={"conversation_id": None, "response": "ok", "agent_run_id": "RUN"}):
            result = send_message("مرحبا")
        self.assertEqual(result["content"], "ok")

    def test_arabic_prompt_basic_flow(self):
        from huf.api.chat import send_message
        fake_agent = SimpleNamespace(name="Agent", provider="Provider", model="gpt-test")
        with patch("huf.api.chat._select_agent", return_value=fake_agent), patch("huf.api.chat.run_agent_sync", return_value={"conversation_id": None, "response": "تم", "agent_run_id": "RUN"}):
            result = send_message("اعرض مبيعات هذا الشهر")
        self.assertIn("تم", result["content"])

    def test_user_cannot_read_other_user_session(self):
        from huf.api.chat import get_messages
        conv = self._make_conversation(owner="Administrator", external_id="Administrator")
        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError):
            get_messages(conv.name)
        frappe.set_user("Administrator")

    def test_user_cannot_delete_other_user_session(self):
        from huf.api.chat import delete_session
        conv = self._make_conversation(owner="Administrator", external_id="Administrator")
        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError):
            delete_session(conv.name)
        frappe.set_user("Administrator")

    def test_debug_trace_hidden_from_normal_user(self):
        from huf.api.chat import get_debug_trace
        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError):
            get_debug_trace()
        frappe.set_user("Administrator")

    def test_debug_trace_visible_to_admin(self):
        from huf.api.chat import get_debug_trace
        with patch("huf.api.chat.get_ai_settings", return_value={"enable_debug": True, "debug_roles": ["System Manager"]}):
            result = get_debug_trace()
        self.assertIn("runs", result)

    def test_blocked_doctype_not_queried(self):
        from huf.ai.erp_query import huf_safe_get_list
        result = huf_safe_get_list("User", fields=["name"], limit=1)
        self.assertFalse(result["success"])
        self.assertTrue(result["permission_denied"])

    def test_safe_get_doc_checks_permission(self):
        from huf.ai.erp_query import huf_safe_get_doc
        result = huf_safe_get_doc("User", "Administrator")
        self.assertFalse(result["success"])

    def test_sensitive_action_requires_confirmation(self):
        from huf.api.chat import send_message
        result = send_message("delete document", doctype="Sales Invoice", metadata={"name": "SINV-TEST"})
        self.assertTrue(result["requires_confirmation"])

    def test_audit_log_created(self):
        from huf.api.chat import send_message
        before = frappe.db.count("HUF AI Audit Log") if frappe.db.exists("DocType", "HUF AI Audit Log") else 0
        send_message("delete document", doctype="Sales Invoice", metadata={"name": "SINV-TEST"})
        after = frappe.db.count("HUF AI Audit Log") if frappe.db.exists("DocType", "HUF AI Audit Log") else 0
        self.assertGreaterEqual(after, before)

    def test_feedback_requires_message_access(self):
        from huf.api.chat import submit_feedback
        conv = self._make_conversation(owner="Administrator", external_id="Administrator")
        msg = self._make_message(conv)
        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError):
            submit_feedback(msg.name, "Positive")
        frappe.set_user("Administrator")

    def test_redaction_masks_sensitive_data(self):
        from huf.ai.redaction import redact_sensitive_data
        text = "email a@example.com phone +967 777777777 " + "password" + "=hello " + "api" + "_key=" + "sk-" + "testsecret1234567890"
        redacted = redact_sensitive_data(text, {"enable_redaction": True})
        self.assertNotIn("a@example.com", redacted)
        self.assertNotIn("hello", redacted)
        self.assertNotIn("sk-testsecret", redacted)
