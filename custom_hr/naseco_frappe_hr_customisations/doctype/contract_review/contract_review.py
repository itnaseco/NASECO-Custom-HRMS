import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from custom_hr.contract_management.services import get_effective_end_date


class ContractReview(Document):
	def validate(self):
		contract = frappe.db.get_value(
			"Employee Contract",
			self.contract,
			["employee", "contract_type", "end_date", "probation_end_date"],
			as_dict=True,
		)
		if not contract:
			frappe.throw(_("Contract does not exist."))
		end_date = get_effective_end_date(contract)
		if not end_date:
			frappe.throw(_("Only a contract with an end or probation date can be reviewed for expiry."))
		if getdate(self.due_date) > getdate(end_date):
			frappe.throw(_("Review due date cannot be after the contract end date."))
		if self.decision != "Pending" and self.review_status not in ("Decided", "Closed"):
			self.review_status = "Decided"

