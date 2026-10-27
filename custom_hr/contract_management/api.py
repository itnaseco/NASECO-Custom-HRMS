from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days

from custom_hr.contract_management.services import get_effective_end_date, require_contract_manager


@frappe.whitelist()
def get_contract_context(employee):
	if not frappe.has_permission("Employee", "read", employee):
		frappe.throw(_("Not permitted to read this employee."), frappe.PermissionError)
	current = frappe.db.get_value(
		"Employee Contract",
		{
			"employee": employee,
			"docstatus": 1,
			"status": ("in", ("Active", "Expiring", "Pending Termination")),
		},
		["name", "status", "contract_type"],
		as_dict=True,
		order_by="start_date desc",
	)
	if not current:
		current = frappe.db.get_value(
			"Employee Contract",
			{"employee": employee, "docstatus": 1, "status": "Scheduled"},
			["name", "status", "contract_type"],
			as_dict=True,
			order_by="start_date asc",
		)
	history_count = frappe.db.count("Employee Contract", {"employee": employee})
	return {
		"current": current,
		"has_contract_history": bool(history_count),
		"contract_count": history_count,
		"can_manage": bool({"HR Manager", "System Manager"} & set(frappe.get_roles())),
	}


@frappe.whitelist(methods=["POST"])
def create_contract(
	employee,
	contract_type,
	start_date,
	contract_duration_months=None,
	has_probation=0,
	probation_duration_months=None,
):
	require_contract_manager()
	if not frappe.db.exists("Employee", employee):
		frappe.throw(_("Employee does not exist."))
	return frappe.get_doc(
		{
			"doctype": "Employee Contract",
			"employee": employee,
			"contract_type": contract_type,
			"contract_duration_months": contract_duration_months,
			"start_date": start_date,
			"change_type": "New",
			"has_probation": has_probation,
			"probation_duration_months": probation_duration_months,
		}
	).insert().name


@frappe.whitelist(methods=["POST"])
def start_contract_review(contract):
	require_contract_manager()
	existing = frappe.db.exists("Contract Review", {"contract": contract})
	if existing:
		return existing
	doc = frappe.get_doc("Employee Contract", contract)
	end_date = get_effective_end_date(doc)
	if not end_date:
		frappe.throw(_("This contract has no reviewable end date."))
	lead_days = frappe.db.get_single_value("Contract Management Settings", "review_lead_days") or 60
	return frappe.get_doc(
		{
			"doctype": "Contract Review",
			"contract": contract,
			"due_date": add_days(end_date, -int(lead_days)),
		}
	).insert().name

