from frappe.tests import UnitTestCase

from custom_hr.contract_management.services import calculate_status


class TestEmployeeContractStatus(UnitTestCase):
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
