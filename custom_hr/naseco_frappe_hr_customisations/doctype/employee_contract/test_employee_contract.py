from types import SimpleNamespace

from frappe.tests import UnitTestCase

from custom_hr.contract_management.services import (
	calculate_contract_end_date,
	calculate_status,
	get_employee_summary_values,
)
from custom_hr.naseco_frappe_hr_customisations.doctype.employee_contract.employee_contract import (
	EmployeeContract,
)


class TestEmployeeContractStatus(UnitTestCase):
	def test_contract_end_date_uses_inclusive_period(self):
		self.assertEqual(str(calculate_contract_end_date("2026-01-01", 12)), "2026-12-31")

	def test_contract_end_date_handles_month_end(self):
		self.assertEqual(str(calculate_contract_end_date("2026-08-31", 1)), "2026-09-30")

	def test_string_duration_from_rpc_is_normalized(self):
		doc = SimpleNamespace(
			contract_type="Fixed Term",
			contract_duration_months="36",
			start_date="2023-02-02",
			end_date=None,
			probation_end_date=None,
		)
		EmployeeContract.set_contract_end_date(doc)
		self.assertEqual(doc.contract_duration_months, 36)
		self.assertEqual(str(doc.end_date), "2026-02-01")

	def test_empty_employee_summary_uses_zero_duration(self):
		values = get_employee_summary_values()
		self.assertEqual(values["custom_contract_duration_months"], 0)
		self.assertIsNone(values["custom_current_contract"])

	def test_scheduled_contract(self):
		doc = self._contract("2026-11-01", "2027-10-31")
		self.assertEqual(calculate_status(doc, "2026-10-26"), "Scheduled")

	def test_active_contract(self):
		doc = self._contract("2026-01-01", "2027-12-31")
		self.assertEqual(calculate_status(doc, "2026-10-26"), "Active")

	def test_expiring_contract(self):
		doc = self._contract("2026-01-01", "2026-11-20")
		self.assertEqual(calculate_status(doc, "2026-10-26"), "Expiring")

	def test_expired_contract(self):
		doc = self._contract("2025-01-01", "2026-10-25")
		self.assertEqual(calculate_status(doc, "2026-10-26"), "Expired")

	def test_terminal_status_is_preserved(self):
		doc = self._contract("2025-01-01", "2027-01-01", status="Terminated")
		self.assertEqual(calculate_status(doc, "2026-10-26"), "Terminated")

	@staticmethod
	def _contract(start_date, end_date, status="Active"):
		return type(
			"ContractStub",
			(),
			{
				"start_date": start_date,
				"end_date": end_date,
				"probation_end_date": None,
				"status": status,
			},
		)()
