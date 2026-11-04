import frappe
from frappe import _
from frappe.model.document import Document


class HUFGuideSettings(Document):
	def validate(self):
		if self.mode != "guide_only":
			frappe.throw(_("AI guidance is not enabled."))
		if self.support_channel and any(x in self.support_channel for x in ("<", ">")):
			frappe.throw(_("Use plain text for the support channel."))
