import frappe

from custom_hr.contract_management.services import reconcile_employee_lifecycle
from custom_hr.setup import install_employee_custom_fields


def execute():
	# Patches run before after_migrate, so ensure lifecycle history fields exist first.
	install_employee_custom_fields()
	employees = frappe.get_all(
		"Employee Contract",
		filters={"docstatus": 1, "status": "Terminated"},
		pluck="employee",
		distinct=True,
	)
	for employee in employees:
		try:
			reconcile_employee_lifecycle(employee)
		except Exception:
			frappe.log_error(
				title=f"Could not reconcile terminated Employee {employee}",
				message=frappe.get_traceback(),
			)
