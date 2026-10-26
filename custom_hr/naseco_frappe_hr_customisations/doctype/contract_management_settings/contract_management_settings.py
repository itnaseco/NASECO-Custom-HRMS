import frappe
from frappe.model.document import Document


class ContractManagementSettings(Document):
	def validate(self):
		values = [
			self.review_lead_days,
			self.first_reminder_days,
			self.first_escalation_days,
			self.final_escalation_days,
		]
		if values != sorted(values, reverse=True):
			frappe.throw("Notification thresholds must descend from review creation to final escalation.")
