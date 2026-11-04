"""bench --site <explicit-site> execute huf.guide.tests.run.run"""

import io
import unittest

import frappe


def run():
	frappe.only_for("System Manager")
	from huf.guide.tests.test_guide import TestGuide
	from huf.guide.tests.test_skill_namespace import TestSkillNamespace
	from huf.guide.tests.test_ux import TestGuideUX

	before = {
		dt: frappe.db.count(dt)
		for dt in ("User", "Contact", "Compendium Page", "HUF Guide Binding", "Form Tour")
	}
	stream = io.StringIO()
	result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
		unittest.TestSuite(
			[
				unittest.defaultTestLoader.loadTestsFromTestCase(TestGuide),
				unittest.defaultTestLoader.loadTestsFromTestCase(TestSkillNamespace),
				unittest.defaultTestLoader.loadTestsFromTestCase(TestGuideUX),
			]
		)
	)
	after = {dt: frappe.db.count(dt) for dt in before}
	output = {
		"tests": result.testsRun,
		"failures": len(result.failures),
		"errors": len(result.errors),
		"skips": len(result.skipped),
		"cleanup_counts_match": before == after,
		"details": stream.getvalue(),
	}
	if not result.wasSuccessful() or before != after:
		print(frappe.as_json(output))
		raise RuntimeError("acceptance_failed")
	return output
