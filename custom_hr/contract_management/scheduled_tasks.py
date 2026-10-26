from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, date_diff, today

from custom_hr.contract_management.services import calculate_status, get_effective_end_date, sync_employee_summary
from custom_hr.naseco_frappe_hr_customisations.doctype.employee_contract.employee_contract import (
	calculate_probation_status,
)


def process_contracts():
	settings = frappe.get_cached_doc("Contract Management Settings")
	if not settings.enabled:
		return
	for row in frappe.get_all(
		"Employee Contract",
		filters={"docstatus": 1, "status": ("in", ("Scheduled", "Active", "Expiring"))},
		fields=["name", "employee", "previous_contract", "end_date", "probation_end_date", "status"],
	):
		process_contract(row, settings)


def process_contract(row, settings):
	doc = frappe.get_doc("Employee Contract", row.name)
	process_probation(doc, settings)
	new_status = calculate_status(doc)
	if new_status != doc.status:
		doc.db_set("status", new_status, update_modified=False)
		if new_status == "Active" and doc.previous_contract:
			previous_status = frappe.db.get_value("Employee Contract", doc.previous_contract, "status")
			if previous_status in ("Scheduled", "Active", "Expiring"):
				frappe.db.set_value("Employee Contract", doc.previous_contract, "status", "Superseded")
		sync_employee_summary(doc if new_status in ("Scheduled", "Active", "Expiring") else None, doc.employee)

	end_date = get_effective_end_date(doc)
	if not end_date or new_status == "Expired":
		if new_status == "Expired":
			notify_expired_active_employee(doc)
		return

	days_left = date_diff(end_date, today())
	if days_left <= int(settings.review_lead_days):
		review = get_or_create_review(doc, settings)
		send_due_notifications(doc, review, days_left, settings)


def get_or_create_review(contract, settings):
	name = frappe.db.exists("Contract Review", {"contract": contract.name})
	if name:
		return frappe.get_doc("Contract Review", name)
	return frappe.get_doc(
		{
			"doctype": "Contract Review",
			"contract": contract.name,
			"due_date": add_days(get_effective_end_date(contract), -int(settings.review_lead_days)),
		}
	).insert(ignore_permissions=True)


def send_due_notifications(contract, review, days_left, settings):
	milestones = [
		(int(settings.review_lead_days), "notified_60_days"),
		(int(settings.first_reminder_days), "notified_30_days"),
		(int(settings.first_escalation_days), "notified_14_days"),
		(int(settings.final_escalation_days), "notified_7_days"),
	]
	for threshold, fieldname in milestones:
		if days_left <= threshold and not review.get(fieldname):
			send_contract_notification(contract, review, days_left, settings.hr_manager_role)
			review.db_set(fieldname, 1, update_modified=False)


def send_contract_notification(contract, review, days_left, manager_role):
	recipients = get_role_emails(manager_role)
	reports_to_user = frappe.db.get_value("Employee", contract.reports_to, "user_id") if contract.reports_to else None
	if reports_to_user:
		recipients.append(reports_to_user)
	recipients = sorted(set(filter(None, recipients)))
	if not recipients:
		return
	frappe.sendmail(
		recipients=recipients,
		subject=_("Contract review due for {0}").format(contract.employee_name),
		message=_(
			"Contract {0} for {1} reaches its end date in {2} day(s). Review record: {3}."
		).format(contract.name, contract.employee_name, days_left, review.name),
		reference_doctype="Contract Review",
		reference_name=review.name,
	)


def get_role_emails(role):
	users = frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent")
	return frappe.get_all(
		"User", filters={"name": ("in", users), "enabled": 1}, pluck="email"
	) if users else []


def process_probation(contract, settings):
	if not contract.has_probation or contract.probation_status in ("Confirmed", "Terminated"):
		return
	new_status = calculate_probation_status(contract)
	if new_status != contract.probation_status:
		contract.db_set("probation_status", new_status, update_modified=False)
		sync_employee_summary(contract)

	days_left = date_diff(contract.probation_end_date, today())
	for threshold in sorted({7, 14, int(settings.probation_review_lead_days or 30)}):
		if days_left <= threshold:
			notify_probation_due(contract, days_left, threshold, settings.hr_manager_role)
			break


def notify_probation_due(contract, days_left, threshold, manager_role):
	key = f"probation-due:{contract.name}:{threshold}"
	if frappe.cache.get_value(key):
		return
	recipients = get_role_emails(manager_role)
	if not recipients:
		return
	frappe.sendmail(
		recipients=recipients,
		subject=_("Probation decision due for {0}").format(contract.employee_name),
		message=_(
			"The probation period on contract {0} reaches its current end date in {1} day(s). "
			"Record confirmation, an agreed extension, or termination before the deadline."
		).format(contract.name, days_left),
		reference_doctype="Employee Contract",
		reference_name=contract.name,
	)
	frappe.cache.set_value(key, 1, expires_in_sec=86400 * 120)


def notify_expired_active_employee(contract):
	if frappe.db.get_value("Employee", contract.employee, "status") != "Active":
		return
	key = f"expired-contract:{contract.name}:{today()}"
	if frappe.cache.get_value(key):
		return
	settings = frappe.get_cached_doc("Contract Management Settings")
	recipients = get_role_emails(settings.hr_manager_role)
	if recipients:
		frappe.sendmail(
			recipients=recipients,
			subject=_("Expired contract requires action: {0}").format(contract.employee_name),
			message=_("Contract {0} has expired while Employee {1} remains active.").format(
				contract.name, contract.employee
			),
			reference_doctype="Employee Contract",
			reference_name=contract.name,
		)
		frappe.cache.set_value(key, 1, expires_in_sec=86400)

