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
	require(len(users) == 2)
	require(
		{u["email"] for u in users}
		== {f"huf.guide.{token}.{p}@example.invalid" for p in ("allowed", "limited")}
	)
	role = "Guide UI Reader " + token
	path = "guide/private-" + token
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
				roles = [role] + (["Compendium Contributor"] if user["persona"] == "allowed" else [])
				frappe.get_doc("User", user["email"]).add_roles(*roles)
			frappe.get_doc(
				{
					"doctype": "Compendium Page",
					"title": "Restricted " + token,
					"path": path,
					"language": "en",
					"published": 1,
					"content": "Confidential sentinel " + token,
					"roles": [{"role": "Compendium Contributor"}],
				}
			).insert()
			frappe.db.commit()
			print(
				json.dumps(
					{
						"created_users": 2,
						"non_admin": all("System Manager" not in frappe.get_roles(u["email"]) for u in users),
					}
				)
			)
		elif data["action"] == "cleanup":
			for name in frappe.get_all("Compendium Page", filters={"path": path}, pluck="name"):
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
		else:
			raise ValueError("invalid_action")
	finally:
		frappe.db.rollback()
		frappe.destroy()


if __name__ == "__main__":
	main()
