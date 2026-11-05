"""Cheap route gates: ordinary Frappe/DIGIT pages never import the AI runtime."""
import frappe
from frappe.website.page_renderers.base_renderer import BaseRenderer


class _LazyRenderer(BaseRenderer):
	prefix = ""
	target = ""

	def can_render(self):
		return self.path == self.prefix or self.path.startswith(self.prefix + "/")

	def render(self):
		return frappe.get_attr(self.target)(self.path, self.http_status_code).render()


class AgentStreamRenderer(_LazyRenderer):
	prefix = "huf/stream"
	target = "huf.ai.agent.stream_renderer.AgentStreamRenderer"


class ApiV1Router(_LazyRenderer):
	prefix = "huf/api/v1"
	target = "huf.api.v1.router.ApiV1Router"
