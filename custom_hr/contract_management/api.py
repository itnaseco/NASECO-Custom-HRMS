from __future__ import annotations

"""Whitelisted endpoints for employee contract and probation management."""

import frappe
from frappe import _
from frappe.utils import add_days, date_diff, today

from custom_hr.contract_management.services import (
	build_successor,
	get_effective_end_date,
	require_contract_manager,
)


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
		[
			"name",
			"status",
			"contract_type",
			"has_probation",
			"probation_status",
			"probation_end_date",
			"probation_review_date",
			"contract_duration_months",
		],
		as_dict=True,
		order_by="start_date desc",
	)
	if not current:
		current = frappe.db.get_value(
			"Employee Contract",
			{"employee": employee, "docstatus": 1, "status": "Scheduled"},
			[
				"name",
				"status",
				"contract_type",
				"has_probation",
				"probation_status",
				"probation_end_date",
				"probation_review_date",
				"contract_duration_months",
			],
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


@frappe.whitelist()
def get_probation_overview(contract):
	"""Return the probation summary and decision trail used by the read-only dialogs."""
	doc = frappe.get_doc("Employee Contract", contract)
	if not frappe.has_permission("Employee Contract", "read", doc=doc):
		frappe.throw(_("Not permitted to read this employee contract."), frappe.PermissionError)
	if not (doc.has_probation or doc.contract_type == "Probationary"):
		frappe.throw(_("This contract does not have a probation period."))
	if not frappe.has_permission("Contract Probation Action", "read"):
		frappe.throw(_("Not permitted to read probation decisions."), frappe.PermissionError)

	history = frappe.get_list(
		"Contract Probation Action",
		filters={"contract": doc.name},
		fields=[
			"name",
			"action_type",
			"decision_date",
			"effective_date",
			"previous_probation_end_date",
			"extension_duration_months",
			"revised_probation_end_date",
			"employee_agreement_date",
			"evaluation_result",
			"reason",
			"evaluation_document",
			"decision_document",
			"employee_agreement_document",
			"approval_notes",
			"docstatus",
			"owner",
			"modified_by",
		],
		order_by="decision_date desc, creation desc",
		limit_page_length=100,
	)
	probation_end_date = doc.probation_end_date or doc.end_date
	return {
		"contract": {
			"name": doc.name,
			"employee": doc.employee,
			"employee_name": doc.employee_name,
			"company": doc.company,
			"contract_type": doc.contract_type,
			"contract_status": doc.status,
			"start_date": doc.start_date,
			"end_date": doc.end_date,
			"probation_duration_months": doc.probation_duration_months,
			"probation_start_date": doc.probation_start_date,
			"original_probation_end_date": doc.original_probation_end_date,
			"probation_end_date": doc.probation_end_date,
			"probation_review_date": doc.probation_review_date,
			"probation_status": doc.probation_status,
			"confirmation_date": doc.confirmation_date,
			"probation_contract_document": doc.probation_contract_document,
		},
		"days_remaining": date_diff(probation_end_date, today()) if probation_end_date else None,
		"history": history,
	}


def _contract_summary(doc):
	return {
		"name": doc.name,
		"employee": doc.employee,
		"employee_name": doc.employee_name,
		"company": doc.company,
		"docstatus": doc.docstatus,
		"status": doc.status,
		"contract_type": doc.contract_type,
		"change_type": doc.change_type,
		"previous_contract": doc.previous_contract,
		"start_date": doc.start_date,
		"end_date": doc.end_date,
		"contract_duration_months": doc.contract_duration_months,
		"next_review_date": doc.next_review_date,
		"has_probation": doc.has_probation,
		"probation_status": doc.probation_status,
		"probation_end_date": doc.probation_end_date,
		"designation": doc.designation,
		"department": doc.department,
		"branch": doc.branch,
		"work_location": doc.work_location,
		"signed_contract": doc.signed_contract,
		"employee_acceptance_date": doc.employee_acceptance_date,
		"termination_category": doc.termination_category,
		"termination_date": doc.termination_date,
		"termination_reason": doc.termination_reason,
		"termination_document": doc.termination_document,
	}


@frappe.whitelist()
def get_contract_overview(contract):
	"""Return a permission-checked contract summary for the Employee dialog."""
	doc = frappe.get_doc("Employee Contract", contract)
	if not frappe.has_permission("Employee Contract", "read", doc=doc):
		frappe.throw(_("Not permitted to read this employee contract."), frappe.PermissionError)
	return _contract_summary(doc)


@frappe.whitelist()
def get_employee_contract_history(employee):
	"""Return every contract version visible to the user for an employee."""
	if not frappe.has_permission("Employee", "read", employee):
		frappe.throw(_("Not permitted to read this employee."), frappe.PermissionError)
	if not frappe.has_permission("Employee Contract", "read"):
		frappe.throw(_("Not permitted to read employee contracts."), frappe.PermissionError)

	names = frappe.get_list(
		"Employee Contract",
		filters={"employee": employee},
		pluck="name",
		order_by="start_date desc, creation desc",
		limit_page_length=100,
	)
	return [_contract_summary(frappe.get_doc("Employee Contract", name)) for name in names]


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
def create_contract_amendment(contract, start_date, duration_months=None):
	doc = frappe.get_doc("Employee Contract", contract)
	return build_successor(
		doc,
		"Amendment",
		start_date,
		duration_months,
		doc.contract_type,
	).name


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
