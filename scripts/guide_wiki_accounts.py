"""Disposable browser identities using existing roles only. Passwords via stdin."""

import argparse
import json
import re
import sys

import frappe


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("--site", required=True)
	args = parser.parse_args()
	data = json.load(sys.stdin)
	token, users = data["token"], data["users"]
	if not re.fullmatch(r"[a-f0-9]{12}", token) or {u["persona"] for u in users} != {
		"employee_ar",
		"employee_en",
		"limited",
	}:
		raise ValueError("invalid_fixture")
	if any(u["email"] != f"huf.wiki.{token}.{u['persona']}@example.invalid" for u in users):
		raise ValueError("invalid_identity")
	frappe.init(site=args.site)
	frappe.connect()
	try:
		for u in users:
			if data["action"] == "create":
				if frappe.db.exists("User", u["email"]) or len(u["password"]) < 30:
					raise ValueError("invalid_new_identity")
				roles = (
					["Compendium Contributor"] if u["persona"] == "limited" else ["Customer Service Officer"]
				)
				doc = frappe.get_doc(
					{
						"doctype": "User",
						"email": u["email"],
						"first_name": "HUF Wiki fixture " + token,
						"new_password": u["password"],
						"language": u["language"],
						"user_type": "System User",
						"send_welcome_email": 0,
						"roles": [{"role": role} for role in roles],
					}
				)
				doc.flags.no_welcome_mail = True
				doc.insert()
				# Remove the automatic Wiki User role from our fixtures: test the
				# existing business-role space contract, not that broad reader role.
				doc = frappe.get_doc("User", u["email"])
				doc.set("roles", [{"role": role} for role in roles])
				doc.save()
				if "System Manager" in frappe.get_roles(u["email"]):
					raise ValueError("admin_fixture")
			elif data["action"] == "cleanup":
				if frappe.db.exists("User", u["email"]):
					if frappe.db.get_value("User", u["email"], "first_name") != "HUF Wiki fixture " + token:
						raise ValueError("identity_mismatch")
					frappe.delete_doc("User", u["email"])
				for name in frappe.get_all("Contact Email", filters={"email_id": u["email"]}, pluck="parent"):
					if frappe.db.get_value("Contact", name, "first_name") != "HUF Wiki fixture " + token:
						raise ValueError("contact_mismatch")
					frappe.delete_doc("Contact", name)
				for dt, field in (("__Auth", "name"), ("DefaultValue", "parent"), ("__UserSettings", "user")):
					frappe.db.delete(dt, {field: u["email"]})
				frappe.clear_cache(user=u["email"])
			else:
				raise ValueError("invalid_action")
		frappe.db.commit()
		counts = {
			dt: sum(frappe.db.count(dt, {field: u["email"]}) for u in users)
			for dt, field in (
				("User", "name"),
				("Has Role", "parent"),
				("DocShare", "user"),
				("Contact Email", "email_id"),
				("__Auth", "name"),
				("DefaultValue", "parent"),
				("__UserSettings", "user"),
			)
		}
		if data["action"] == "cleanup" and any(counts.values()):
			raise ValueError("cleanup_incomplete")
		print(json.dumps({"action": data["action"], "owned_counts": counts, "existing_roles_only": True}))
	finally:
		frappe.db.rollback()
		frappe.destroy()


if __name__ == "__main__":
	main()
