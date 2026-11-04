import frappe
from frappe import _
from frappe.model.document import Document

from huf.guide import knowledge


class HUFGuideBinding(Document):
	def validate(self):
		self.article_path = knowledge.logical_path(self.article_path)
		knowledge.read(self.article_path)
		target = {"Page": "Page", "Workspace": "Workspace", "Form": "DocType", "List": "DocType"}.get(
			self.screen_type
		)
		if not target or not frappe.db.exists(target, self.screen_name):
			frappe.throw(_("Choose an existing screen."))
		if self.fieldname and (
			self.screen_type != "Form" or not frappe.get_meta(self.screen_name).get_field(self.fieldname)
		):
			frappe.throw(_("Choose an existing field on this form."))
		if self.form_tour:
			tour = frappe.get_doc("Form Tour", self.form_tour)
			if tour.ui_tour:
				name = (
					tour.page_name
					if self.screen_type == "Page"
					else tour.workspace_name
					if self.screen_type == "Workspace"
					else tour.reference_doctype
				)
				if (
					tour.view_name != ("Workspaces" if self.screen_type == "Workspace" else self.screen_type)
					or name != self.screen_name
				):
					frappe.throw(_("The tour must belong to the selected screen."))
			elif self.screen_type != "Form" or tour.reference_doctype != self.screen_name:
				frappe.throw(_("The tour must belong to the selected screen."))
			if tour.save_on_complete:
				frappe.throw(_("Guide tours must not save documents."))
