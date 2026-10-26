from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, add_months, add_years, cint, getdate, today

ACTIVE_STATUSES = ("Scheduled", "Active", "Expiring")
OPEN_PROBATION_STATUSES = ("Pending", "Under Probation", "Evaluation Due", "Extended", "Decision Overdue")
SUMMARY_FIELDS = {
	"custom_current_contract": "name",
	"custom_contract_type": "contract_type",
	"custom_contract_duration_months": "contract_duration_months",
	"custom_contract_start_date": "start_date",
	"custom_probation_end_date": "probation_end_date",
	"custom_probation_status": "probation_status",
	"custom_confirmation_date": "confirmation_date",
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
	return doc.probation_end_date if doc.contract_type == "Probationary" else doc.end_date


def has_open_probation(doc):
	if not (getattr(doc, "has_probation", 0) or doc.contract_type == "Probationary"):
		return False
	if doc.status == "Scheduled":
		return False
	return (getattr(doc, "probation_status", None) or "Under Probation") in OPEN_PROBATION_STATUSES


def is_probation_review_window_open(doc, reference_date=None):
	review_date = getattr(doc, "probation_review_date", None)
	if not review_date:
		return False
	return getdate(reference_date or today()) >= getdate(review_date)


def calculate_contract_end_date(start_date, duration_months):
	"""Return the inclusive last day of a whole-month contract period."""
	return add_months(add_days(start_date, -1), cint(duration_months))


def get_probation_review_lead_days():
	return cint(frappe.db.get_single_value("Contract Management Settings", "probation_review_lead_days")) or 30


def get_employee_summary_values(contract=None):
	values = {
		fieldname: (contract.get(source) if contract else None)
		for fieldname, source in SUMMARY_FIELDS.items()
	}
	# MariaDB stores Frappe Int fields as NOT NULL. Use zero when there is no
	# current duration, including permanent and expired contracts.
	values["custom_contract_duration_months"] = cint(
		values.get("custom_contract_duration_months")
	)
	values["custom_has_probation"] = cint(contract.get("has_probation")) if contract else 0
	values["custom_contract_end_date"] = get_effective_end_date(contract) if contract else None
	return values


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
	if doc.previous_contract and doc.change_type == "Amendment":
		filters["name"] = ("not in", (doc.name or "", doc.previous_contract))
	for row in frappe.get_all(
		"Employee Contract", filters=filters, fields=["name", "contract_type", "end_date", "probation_end_date"]
	):
		existing_end = get_effective_end_date(row)
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
	values = get_employee_summary_values(contract)
	frappe.db.set_value("Employee", employee, values, update_modified=False)


def get_allowed_successor_actions(source):
	if source.docstatus != 1 or source.status in ("Terminated", "Superseded"):
		return []
	if source.status == "Scheduled":
		return ["Amendment"]
	if has_open_probation(source):
		return ["Amendment"]
	if source.status == "Expired":
		return ["Renewal"] if source.contract_type == "Fixed Term" else []
	if source.contract_type == "Probationary":
		return ["Extension", "Confirmation", "Amendment"]
	if source.contract_type == "Fixed Term":
		return ["Extension", "Renewal", "Amendment"]
	if source.contract_type == "Permanent":
		return ["Amendment"]
	return []


def validate_successor_transition(source, change_type, start_date, contract_type):
	allowed = get_allowed_successor_actions(source)
	if change_type not in allowed:
		frappe.throw(
			_("{0} is not allowed for a {1} contract with status {2}.").format(
				change_type, source.contract_type, source.status
			)
		)

	contract_type = contract_type or source.contract_type
	if change_type in ("Renewal", "Extension") and contract_type != source.contract_type:
		frappe.throw(_("A {0} must retain the existing contract type.").format(change_type.lower()))
	if change_type == "Confirmation" and contract_type == "Probationary":
		frappe.throw(_("Confirmation must create a Fixed Term or Permanent contract."))
	if change_type == "Amendment" and contract_type != source.contract_type:
		frappe.throw(_("Use Renewal or Confirmation to change the contract type."))

	end_date = get_effective_end_date(source)
	if change_type in ("Renewal", "Extension", "Confirmation") and end_date:
		if not start_date:
			frappe.throw(_("A start date is required for {0}.").format(change_type.lower()))
		minimum_start = add_days(end_date, 1)
		if getdate(start_date) < getdate(minimum_start):
			frappe.throw(
				_("{0} must start on or after {1}, after the current contract ends.").format(
					change_type, frappe.format_value(minimum_start, {"fieldtype": "Date"})
				)
			)
	return contract_type


def build_successor(source, change_type, start_date, duration_months=None, contract_type=None):
	require_contract_manager()
	contract_type = validate_successor_transition(source, change_type, start_date, contract_type)
	data = source.as_dict(no_nulls=False)
	for key in ("name", "owner", "creation", "modified", "modified_by", "docstatus", "idx", "status"):
		data.pop(key, None)
	data.update(
		{
			"doctype": "Employee Contract",
			"previous_contract": source.name,
			"change_type": change_type,
			"start_date": start_date,
			"contract_duration_months": duration_months if contract_type != "Permanent" else None,
			"end_date": None,
			"probation_end_date": None,
			"contract_type": contract_type,
			"signed_contract": None,
			"employee_acceptance_date": None,
			"termination_category": None,
			"termination_date": None,
			"termination_reason": None,
		},
	)
	if change_type != "Amendment":
		data.update(
			{
				"has_probation": 0,
				"probation_duration_months": None,
				"probation_start_date": None,
				"original_probation_end_date": None,
				"probation_end_date": None,
				"probation_review_date": None,
				"probation_status": "Not Applicable",
				"confirmation_date": None,
				"probation_contract_document": None,
			}
		)
	return frappe.get_doc(data).insert()


def terminate_contract(contract, category, termination_date, reason, probation_action=False):
	require_contract_manager()
	if contract.docstatus != 1 or contract.status in ("Terminated", "Superseded", "Expired"):
		frappe.throw(_("This contract cannot be terminated in its current state."))
	if has_open_probation(contract) and not probation_action:
		frappe.throw(
			_("Use Terminate During Probation while the employee's probation decision is unresolved.")
		)
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
