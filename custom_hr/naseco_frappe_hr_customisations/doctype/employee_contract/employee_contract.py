from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, add_months, cint, date_diff, getdate, today

from custom_hr.contract_management.services import (
	ACTIVE_STATUSES,
	build_successor,
	calculate_contract_end_date,
	calculate_status,
	get_effective_end_date,
	get_probation_review_lead_days,
	require_contract_manager,
	set_projected_retirement_date,
	sync_employee_summary,
	terminate_contract,
	validate_no_overlap,
)


class EmployeeContract(Document):
	def validate(self):
		self.validate_employee()
		self.set_contract_end_date()
		self.validate_dates_and_type()
		self.set_and_validate_probation()
		set_projected_retirement_date(self)
		end_date = get_effective_end_date(self)
		self.next_review_date = add_days(end_date, -60) if end_date else None
		if self.docstatus == 0:
			self.status = "Draft"

	def before_submit(self):
		require_contract_manager()
		if not self.signed_contract or not self.employee_acceptance_date:
			frappe.throw(_("Signed contract and employee acceptance date are required before submission."))
		validate_no_overlap(self)
		self.status = calculate_status(self)
		if self.has_probation:
			self.probation_status = calculate_probation_status(self)

	def on_submit(self):
		if self.previous_contract and getdate(self.start_date) <= getdate():
			previous = frappe.get_doc("Employee Contract", self.previous_contract)
			if previous.status in ACTIVE_STATUSES:
				previous.db_set("status", "Superseded")
		sync_employee_summary(self)

	def before_cancel(self):
		require_contract_manager()

	def on_cancel(self):
		sync_employee_summary(employee=self.employee)

	def validate_employee(self):
		if not frappe.db.exists("Employee", self.employee):
			frappe.throw(_("Employee does not exist."))
		if self.previous_contract:
			previous_employee = frappe.db.get_value("Employee Contract", self.previous_contract, "employee")
			if previous_employee != self.employee:
				frappe.throw(_("Previous contract must belong to the same employee."))

	def validate_dates_and_type(self):
		if self.is_new() and self.change_type == "New" and self.contract_type == "Probationary":
			frappe.throw(
				_("Create a Fixed Term or Permanent contract and enable Has Probation instead.")
			)
		if self.contract_type == "Fixed Term":
			if not self.end_date or getdate(self.end_date) <= getdate(self.start_date):
				frappe.throw(_("Fixed Term end date must be after the start date."))
			self.probation_end_date = None
		elif self.contract_type == "Probationary":
			if not self.probation_end_date or getdate(self.probation_end_date) <= getdate(self.start_date):
				frappe.throw(_("Probation end date must be after the start date."))
			self.end_date = None
		else:
			self.contract_duration_months = None
			self.end_date = None
			self.probation_end_date = None

	def set_contract_end_date(self):
		if self.contract_type == "Permanent":
			return
		self.contract_duration_months = cint(self.contract_duration_months)
		if self.contract_duration_months <= 0:
			frappe.throw(_("Contract duration must be a positive number of months."))
		end_date = calculate_contract_end_date(self.start_date, self.contract_duration_months)
		if self.contract_type == "Probationary":
			self.probation_end_date = end_date
			self.end_date = None
		else:
			self.end_date = end_date

	def set_and_validate_probation(self):
		# Keep the former standalone Probationary contract behavior for legacy data.
		if self.contract_type == "Probationary":
			self.has_probation = 1
			self.probation_start_date = self.start_date
			self.original_probation_end_date = self.original_probation_end_date or self.probation_end_date
			self.probation_review_date = add_days(self.probation_end_date, -get_probation_review_lead_days())
			self.validate_legacy_probation()
			return

		if not self.has_probation:
			self.probation_duration_months = None
			self.probation_start_date = None
			self.original_probation_end_date = None
			self.probation_end_date = None
			self.probation_review_date = None
			self.probation_status = "Not Applicable"
			self.confirmation_date = None
			return

		if self.change_type not in ("New", "Amendment"):
			frappe.throw(_("Probation can only be assigned when creating a new employment contract."))
		months = cint(self.probation_duration_months)
		if months <= 0 or months > 6:
			frappe.throw(_("The initial probation period must be between one and six months."))
		self.probation_duration_months = months
		self.probation_start_date = self.start_date
		calculated_end = calculate_contract_end_date(self.start_date, months)
		if self.change_type == "New" or not self.original_probation_end_date:
			self.original_probation_end_date = calculated_end
		if self.change_type == "New" or not self.probation_end_date:
			self.probation_end_date = calculated_end
		self.probation_review_date = add_days(self.probation_end_date, -get_probation_review_lead_days())
		if self.end_date and getdate(self.probation_end_date) > getdate(self.end_date):
			frappe.throw(_("Probation cannot extend beyond the employment contract end date."))
		if self.probation_status not in ("Extended", "Confirmed", "Terminated"):
			self.probation_status = calculate_probation_status(self)

	def validate_legacy_probation(self):
		if self.contract_type != "Probationary":
			return
		months = date_diff(self.probation_end_date, self.start_date)
		is_extension = self.change_type == "Extension" and self.previous_contract
		if is_extension:
			previous = frappe.get_doc("Employee Contract", self.previous_contract)
			if previous.contract_type != "Probationary":
				frappe.throw(_("A probation extension must follow a probationary contract."))
			if months > date_diff(add_months(self.start_date, 6), self.start_date):
				frappe.throw(_("A probation extension cannot exceed six months."))
			other_extension = frappe.db.exists(
				"Employee Contract",
				{
					"employee": self.employee,
					"contract_type": "Probationary",
					"change_type": "Extension",
					"docstatus": ("!=", 2),
					"name": ("!=", self.name or ""),
				},
			)
			if other_extension:
				frappe.throw(_("Probation may only be extended once ({0}).").format(other_extension))
		else:
			if getdate(self.probation_end_date) > add_months(self.start_date, 6):
				frappe.throw(_("Initial probation cannot exceed six months."))
			existing = frappe.db.exists(
				"Employee Contract",
				{
					"employee": self.employee,
					"contract_type": "Probationary",
					"docstatus": ("!=", 2),
					"name": ("!=", self.name or ""),
				},
			)
			if existing:
				frappe.throw(_("Employee has already had a probationary contract ({0}).").format(existing))

	@frappe.whitelist(methods=["POST"])
	def make_successor(self, change_type, start_date, duration_months=None, contract_type=None):
		return build_successor(self, change_type, start_date, duration_months, contract_type).name

	@frappe.whitelist(methods=["POST"])
	def terminate(self, category, termination_date, reason):
		terminate_contract(self, category, termination_date, reason)
		return self.name


def calculate_probation_status(doc, reference_date=None):
	if not doc.has_probation and doc.contract_type != "Probationary":
		return "Not Applicable"
	if doc.probation_status in ("Confirmed", "Terminated"):
		return doc.probation_status
	reference_date = getdate(reference_date or today())
	if getdate(doc.probation_start_date or doc.start_date) > reference_date:
		return "Pending"
	if getdate(doc.probation_end_date) < reference_date:
		return "Decision Overdue"
	if getdate(doc.probation_end_date) <= add_days(reference_date, 30):
		return "Evaluation Due"
	return "Extended" if doc.probation_status == "Extended" else "Under Probation"
