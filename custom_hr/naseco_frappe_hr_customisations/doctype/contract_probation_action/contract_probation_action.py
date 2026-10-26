from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, add_months, cint, getdate

from custom_hr.contract_management.services import (
	get_probation_review_lead_days,
	require_contract_manager,
	sync_employee_summary,
	terminate_contract,
)


class ContractProbationAction(Document):
	def validate(self):
		self.validate_contract()
		self.set_extension_end_date()
		self.validate_decision()

	def before_submit(self):
		require_contract_manager()
		frappe.db.sql("select name from `tabEmployee Contract` where name=%s for update", self.contract)
		self.validate_contract()
		self.validate_decision()
		if not self.evaluation_document or not self.decision_document:
			frappe.throw(_("The probation evaluation and decision letter are required before submission."))

	def on_submit(self):
		contract = frappe.get_doc("Employee Contract", self.contract)
		if self.action_type == "Confirmation":
			contract.db_set(
				{"probation_status": "Confirmed", "confirmation_date": self.effective_date},
				update_modified=False,
			)
		elif self.action_type == "Extension":
			contract.db_set(
				{
					"probation_status": "Extended",
					"probation_end_date": self.revised_probation_end_date,
					"probation_review_date": add_days(
						self.revised_probation_end_date, -get_probation_review_lead_days()
					),
				},
				update_modified=False,
			)
		else:
			terminate_contract(
				contract,
				"Poor-performance Dismissal",
				self.effective_date,
				self.reason,
				probation_action=True,
			)
			contract.db_set("probation_status", "Terminated", update_modified=False)
		sync_employee_summary(employee=contract.employee)

	def before_cancel(self):
		require_contract_manager()
		frappe.throw(_("Submitted probation decisions are part of the employment audit trail and cannot be cancelled."))

	def validate_contract(self):
		contract = frappe.get_doc("Employee Contract", self.contract)
		if contract.docstatus != 1 or not (contract.has_probation or contract.contract_type == "Probationary"):
			frappe.throw(_("Select a submitted contract with an applicable probation period."))
		if contract.status in ("Terminated", "Superseded", "Expired"):
			frappe.throw(_("Probation decisions cannot be recorded against a {0} contract.").format(contract.status))
		if contract.probation_status in ("Confirmed", "Terminated"):
			frappe.throw(_("Probation has already been {0}.").format(contract.probation_status.lower()))
		if getdate(self.effective_date) < getdate(contract.start_date):
			frappe.throw(_("The effective date cannot precede the contract start date."))

	def set_extension_end_date(self):
		if self.action_type != "Extension":
			self.extension_duration_months = None
			self.revised_probation_end_date = None
			self.employee_agreement_date = None
			self.employee_agreement_document = None
			return
		months = cint(self.extension_duration_months)
		if months <= 0 or months > 6:
			frappe.throw(_("A probation extension must be between one and six months."))
		self.extension_duration_months = months
		if not self.previous_probation_end_date:
			self.previous_probation_end_date = frappe.db.get_value(
				"Employee Contract", self.contract, "probation_end_date"
			)
		if not self.previous_probation_end_date:
			frappe.throw(_("The contract does not have a current probation end date."))
		self.revised_probation_end_date = add_months(self.previous_probation_end_date, months)

	def validate_decision(self):
		contract = frappe.get_doc("Employee Contract", self.contract)
		if self.action_type == "Extension":
			if frappe.db.exists(
				"Contract Probation Action",
				{
					"contract": self.contract,
					"action_type": "Extension",
					"docstatus": 1,
					"name": ("!=", self.name or ""),
				},
			):
				frappe.throw(_("Probation may only be extended once."))
			maximum_end = add_months(contract.original_probation_end_date, 6)
			if getdate(self.revised_probation_end_date) > getdate(maximum_end):
				frappe.throw(_("Total probation extension cannot exceed six months."))
			if contract.end_date and getdate(self.revised_probation_end_date) > getdate(contract.end_date):
				frappe.throw(_("Probation cannot extend beyond the employment contract end date."))
			if not self.employee_agreement_date or not self.employee_agreement_document:
				frappe.throw(_("Employee agreement and the signed agreement document are required for extension."))
