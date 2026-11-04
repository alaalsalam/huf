"""Owned disposable UI fixtures. Explicit site; credentials accepted on stdin only."""

import argparse
import json
import re
import sys

import frappe


def require(condition):
	if not condition:
		raise ValueError("invalid_fixture")


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("--site", required=True)
	args = parser.parse_args()
	data = json.load(sys.stdin)
	token = data["token"]
	require(re.fullmatch("[a-f0-9]{12}", token))
	users = data["users"]
	personas = {"allowed", "limited", "admin"} if len(users) == 3 else {"allowed", "limited"}
	require({u["email"] for u in users} == {f"huf.guide.{token}.{p}@example.invalid" for p in personas})
	role = "Guide UI Reader " + token
	path = "guide/private-" + token
	service_path = "guide/service-" + token
	binding_name = "guide-ui-service-" + token
	tour_name = "Guide UI Tour " + token
	frappe.init(site=args.site)
	frappe.connect()
	frappe.set_user("Administrator")
	try:
		if data["action"] == "create":
			require(not frappe.db.exists("Role", role))
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert()
			for user in users:
				require(not frappe.db.exists("User", user["email"]))
				require(len(user["password"]) >= 30)
				doc = frappe.get_doc(
					{
						"doctype": "User",
						"email": user["email"],
						"first_name": "Guide UI fixture " + token,
						"language": user["language"],
						"new_password": user["password"],
						"send_welcome_email": 0,
						"user_type": "System User",
						"roles": [{"role": role}],
					}
				)
				doc.flags.no_welcome_mail = True
				doc.insert()
				roles = [role] + (
					["Compendium Contributor"]
					if user["persona"] == "allowed"
					else ["System Manager"]
					if user["persona"] == "admin"
					else []
				)
				frappe.get_doc("User", user["email"]).add_roles(*roles)
			page = frappe.get_doc(
				{
					"doctype": "Compendium Page",
					"title": "Restricted " + token,
					"path": path,
					"language": "en",
					"published": 1,
					"content": "Confidential sentinel "
					+ token
					+ "\n\n![remote](https://tracking.invalid/guide.png)",
					"roles": [{"role": "Compendium Contributor"}],
				}
			).insert()
			if data.get("ux"):
				for language, title, content in (
					(
						"en",
						"Synthetic guide service",
						"Synthetic test only: enter the mandatory title. This does not approve publication.",
					),
					(
						"ar",
						"خدمة دليل صناعية",
						"اختبار صناعي فقط: أدخل العنوان الإلزامي. لا يثبت الفحص اعتماد النشر.",
					),
				):
					frappe.get_doc(
						{
							"doctype": "Compendium Page",
							"title": title,
							"language": language,
							"path": service_path,
							"published": 1,
							"content": content,
						}
					).insert()
				frappe.get_doc(
					{
						"doctype": "Form Tour",
						"title": tour_name,
						"ui_tour": 1,
						"view_name": "Form",
						"reference_doctype": "Compendium Page",
						"track_steps": 0,
						"steps": [
							{
								"ui_tour": 1,
								"title": "Title",
								"description": "Synthetic test only",
								"element_selector": ".frappe-control[data-fieldname='title']",
								"position": "Bottom",
							}
						],
					}
				).insert()
				frappe.get_doc(
					{
						"doctype": "HUF Guide Binding",
						"screen_type": "Form",
						"screen_name": "Compendium Page",
						"article_path": service_path,
						"form_tour": tour_name,
						"next_instruction": "Enter the mandatory title. Synthetic test only.",
						"target_type": "Form",
						"target_name": "Compendium Page",
						"target_field": "title",
						"record_check_enabled": 1,
						"record_check": "native_required_fields",
						"check_roles": [{"role": role}],
						"check_fields": "title",
						"complete_instruction": "Specified fields present; this does not approve publication.",
						"incomplete_instruction": "Enter the mandatory title. Synthetic test only.",
					}
				).insert(set_name=binding_name)
			frappe.db.commit()
			print(
				json.dumps(
					{
						"created_users": len(users),
						"non_admin": all(
							"System Manager" not in frappe.get_roles(u["email"])
							for u in users
							if u["persona"] != "admin"
						),
						"document": page.name,
						"binding": binding_name,
						"original_checks": frappe.db.get_single_value(
							"HUF Guide Settings", "record_checks_enabled"
						),
					}
				)
			)
		elif data["action"] == "cleanup":
			if data.get("ux"):
				if frappe.db.exists("HUF Guide Binding", binding_name):
					frappe.delete_doc("HUF Guide Binding", binding_name)
				if frappe.db.exists("Form Tour", tour_name):
					frappe.delete_doc("Form Tour", tour_name)
				frappe.db.set_single_value(
					"HUF Guide Settings", "record_checks_enabled", data["original_checks"]
				)
			for name in frappe.get_all(
				"Compendium Page", filters={"path": ["in", [path, service_path]]}, pluck="name"
			):
				frappe.delete_doc("Compendium Page", name)
			for user in users:
				email = user["email"]
				if frappe.db.exists("User", email):
					require(frappe.db.get_value("User", email, "first_name") == "Guide UI fixture " + token)
					frappe.delete_doc("User", email)
				for contact in set(
					frappe.get_all("Contact Email", filters={"email_id": email}, pluck="parent")
				):
					require(
						frappe.db.get_value("Contact", contact, "first_name") == "Guide UI fixture " + token
					)
					frappe.delete_doc("Contact", contact)
				for dt, field in (("__Auth", "name"), ("DefaultValue", "parent"), ("__UserSettings", "user")):
					frappe.db.delete(dt, {field: email})
				frappe.clear_cache(user=email)
			if frappe.db.exists("Role", role):
				frappe.delete_doc("Role", role)
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
			require(not any(counts.values()))
			print(json.dumps({"remaining_fixture_rows": counts}))
		elif data.get("ux") and data["action"] in (
			"enable_checks",
			"make_incomplete",
			"make_complete",
			"unknown_instruction",
			"withdraw_role",
			"unpublish",
		):
			page_name = frappe.db.get_value("Compendium Page", {"path": path}, "name")
			require(page_name)
			if data["action"] == "enable_checks":
				frappe.db.set_single_value("HUF Guide Settings", "record_checks_enabled", 1)
			elif data["action"] == "make_incomplete":
				frappe.db.set_value("Compendium Page", page_name, "title", "")
			elif data["action"] == "make_complete":
				frappe.db.set_value("Compendium Page", page_name, "title", "Restricted " + token)
			elif data["action"] == "unknown_instruction":
				frappe.db.set_value("HUF Guide Binding", binding_name, "complete_instruction", "")
			elif data["action"] == "withdraw_role":
				frappe.get_doc("User", f"huf.guide.{token}.allowed@example.invalid").remove_roles(
					"Compendium Contributor"
				)
			else:
				frappe.db.set_value("Compendium Page", page_name, "published", 0)
			frappe.db.commit()
			print(json.dumps({"owned_fixture_action": data["action"]}))
		else:
			raise ValueError("invalid_action")
	finally:
		frappe.db.rollback()
		frappe.destroy()


if __name__ == "__main__":
	main()
