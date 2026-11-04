import frappe
from frappe import _
from frappe.model.document import Document

from huf.guide import policy


class HUFGuideSettings(Document):
	def validate(self):
		if self.mode != "guide_only":
			frappe.throw(_("AI guidance is not enabled."))
		if self.support_channel and any(x in self.support_channel for x in ("<", ">")):
			frappe.throw(_("Use plain text for the support channel."))
		for value in (self.included_screens, self.excluded_screens):
			for rule in policy.screen_rules(value):
				kind, separator, name = rule.partition(":")
				dt = {"Page": "Page", "Form": "DocType", "List": "DocType", "Workspace": "Workspace"}.get(
					kind
				)
				if not separator or not dt or not frappe.db.exists(dt, name):
					frappe.throw(_("Use an existing screen in the format Page:docs or Form:ToDo."))
