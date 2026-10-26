from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, add_years, cint, getdate, today

ACTIVE_STATUSES = ("Scheduled", "Active", "Expiring")
SUMMARY_FIELDS = {
	"custom_current_contract": "name",
	"custom_contract_type": "contract_type",
	"custom_contract_start_date": "start_date",
	"custom_contract_end_date": "end_date",
	"custom_probation_end_date": "probation_end_date",
	"custom_contract_status": "status",
	"custom_next_contract_review_date": "next_review_date",
	"custom_projected_retirement_date": "projected_retirement_date",
}


def has_contract_manager_role() -> bool:
	return bool({"HR Manager", "System Manager"} & set(frappe.get_roles()))


def require_contract_manager():
	if not has_contract_manager_role():
		frappe.throw(_("Only an HR Manager may perform this contract action."), frappe.PermissionError)


def get_effective_end_date(doc):
	return doc.end_date or doc.probation_end_date


def calculate_status(doc, reference_date=None):
	reference_date = getdate(reference_date or today())
	if doc.status in ("Terminated", "Superseded"):
		return doc.status
	if getdate(doc.start_date) > reference_date:
		return "Scheduled"
	end_date = get_effective_end_date(doc)
	if end_date and getdate(end_date) < reference_date:
		return "Expired"
	if end_date and getdate(end_date) <= add_days(reference_date, 30):
		return "Expiring"
	return "Active"


def validate_no_overlap(doc):
	# Serialise contract activation/submission per employee to close the race
	# between the overlap check and the insert/update in concurrent requests.
	frappe.db.sql("select name from `tabEmployee` where name=%s for update", doc.employee)
	end_date = get_effective_end_date(doc)
	filters = {
		"employee": doc.employee,
		"docstatus": 1,
		"status": ("in", ACTIVE_STATUSES),
		"name": ("!=", doc.name or ""),
		"start_date": ("<=", end_date or "9999-12-31"),
	}
	for row in frappe.get_all(
		"Employee Contract", filters=filters, fields=["name", "end_date", "probation_end_date"]
	):
		existing_end = row.end_date or row.probation_end_date
		if not existing_end or getdate(existing_end) >= getdate(doc.start_date):
			frappe.throw(_("Contract dates overlap with {0}.").format(frappe.bold(row.name)))


def sync_employee_summary(contract=None, employee=None):
	employee = employee or contract.employee
	if not employee or not frappe.db.exists("Employee", employee):
		return
	if contract is None or contract.status not in ACTIVE_STATUSES:
		name = frappe.db.get_value(
			"Employee Contract",
			{"employee": employee, "docstatus": 1, "status": ("in", ("Active", "Expiring"))},
			"name",
			order_by="start_date desc",
		)
		if not name:
			name = frappe.db.get_value(
				"Employee Contract",
				{"employee": employee, "docstatus": 1, "status": "Scheduled"},
				"name",
				order_by="start_date asc",
			)
		contract = frappe.get_doc("Employee Contract", name) if name else None
	elif contract.status == "Scheduled":
		active_name = frappe.db.get_value(
			"Employee Contract",
			{
				"employee": employee,
				"docstatus": 1,
				"status": ("in", ("Active", "Expiring")),
				"name": ("!=", contract.name),
			},
			"name",
			order_by="start_date desc",
		)
		if active_name:
			contract = frappe.get_doc("Employee Contract", active_name)
	values = {
		fieldname: (contract.get(source) if contract else None)
		for fieldname, source in SUMMARY_FIELDS.items()
	}
	frappe.db.set_value("Employee", employee, values, update_modified=False)


def build_successor(source, change_type, start_date, end_date=None, contract_type=None):
	require_contract_manager()
	if source.docstatus != 1 or source.status not in ACTIVE_STATUSES:
		frappe.throw(_("Only an active or scheduled submitted contract can have a successor."))
	data = source.as_dict(no_nulls=False)
	for key in ("name", "owner", "creation", "modified", "modified_by", "docstatus", "idx", "status"):
		data.pop(key, None)
	contract_type = contract_type or source.contract_type
	data.update(
		{
			"doctype": "Employee Contract",
			"previous_contract": source.name,
			"change_type": change_type,
			"start_date": start_date,
			"end_date": end_date if contract_type == "Fixed Term" else None,
			"probation_end_date": end_date if contract_type == "Probationary" else None,
			"contract_type": contract_type,
			"signed_contract": None,
			"employee_acceptance_date": None,
			"termination_category": None,
			"termination_date": None,
			"termination_reason": None,
		},
	)
	return frappe.get_doc(data).insert()


def terminate_contract(contract, category, termination_date, reason):
	require_contract_manager()
	if contract.docstatus != 1 or contract.status in ("Terminated", "Superseded", "Expired"):
		frappe.throw(_("This contract cannot be terminated in its current state."))
	if getdate(termination_date) < getdate(contract.start_date):
		frappe.throw(_("Termination date cannot precede the contract start date."))
	if not category or not reason:
		frappe.throw(_("Termination category and reason are required."))
	contract.db_set(
		{
			"status": "Terminated",
			"termination_category": category,
			"termination_date": termination_date,
			"termination_reason": reason,
		},
	)
	sync_employee_summary(employee=contract.employee)


def set_projected_retirement_date(doc):
	if doc.contract_type == "Permanent" and doc.retirement_age:
		date_of_birth = frappe.db.get_value("Employee", doc.employee, "date_of_birth")
		doc.projected_retirement_date = add_years(date_of_birth, cint(doc.retirement_age)) if date_of_birth else None
	else:
		doc.projected_retirement_date = None
