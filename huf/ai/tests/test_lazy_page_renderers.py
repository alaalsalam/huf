import unittest
from unittest.mock import Mock, patch
from huf.ai import page_renderers


class TestLazyRenderers(unittest.TestCase):
	def test_regular_pages_and_lookalike_prefixes_never_load_ai(self):
		with patch.object(page_renderers.frappe, "get_attr") as load:
			for cls in [page_renderers.AgentStreamRenderer, page_renderers.ApiV1Router]:
				for path in ["digit", "digit/pro/dashboard", "mostaad", "huf", cls.prefix + "-other"]:
					self.assertFalse(cls(path).can_render(), path)
			load.assert_not_called()

	def test_matched_route_retains_native_renderer_and_status(self):
		for cls in [page_renderers.AgentStreamRenderer, page_renderers.ApiV1Router]:
			for path in [cls.prefix, cls.prefix + "/child"]:
				target = Mock()
				with patch.object(page_renderers.frappe, "get_attr", return_value=target) as load:
					renderer = cls(path, 202)
					self.assertTrue(renderer.can_render())
					load.assert_not_called()
					self.assertEqual(renderer.render(), target.return_value.render.return_value)
					load.assert_called_once_with(cls.target)
					target.assert_called_once_with(path, 202)
