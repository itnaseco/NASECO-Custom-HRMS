from types import SimpleNamespace

import frappe
from frappe.tests import UnitTestCase

from custom_hr.contract_management.services import (
	calculate_contract_end_date,
	calculate_status,
	get_effective_end_date,
	get_allowed_successor_actions,
	get_employee_summary_values,
	is_probation_review_window_open,
	validate_successor_transition,
)
from custom_hr.naseco_frappe_hr_customisations.doctype.employee_contract.employee_contract import (
	EmployeeContract,
	calculate_probation_status,
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
		self.assertEqual(values["custom_has_probation"], 0)

	def test_fixed_term_probation_is_inside_full_contract(self):
		doc = SimpleNamespace(
			contract_type="Fixed Term",
			change_type="New",
			has_probation=1,
			probation_duration_months="6",
			start_date="2026-01-01",
			end_date="2028-12-31",
			probation_start_date=None,
			original_probation_end_date=None,
			probation_end_date=None,
			probation_review_date=None,
			probation_status=None,
			confirmation_date=None,
			docstatus=0,
		)
		EmployeeContract.set_and_validate_probation(doc)
		self.assertEqual(str(doc.probation_end_date), "2026-06-30")
		self.assertEqual(str(doc.end_date), "2028-12-31")
		self.assertEqual(str(doc.probation_review_date), "2026-05-31")

	def test_probation_status_becomes_due_then_overdue(self):
		doc = SimpleNamespace(
			contract_type="Fixed Term",
			has_probation=1,
			start_date="2026-01-01",
			probation_start_date="2026-01-01",
			probation_end_date="2026-06-30",
			probation_status="Under Probation",
		)
		self.assertEqual(calculate_probation_status(doc, "2026-06-01"), "Evaluation Due")
		self.assertEqual(calculate_probation_status(doc, "2026-07-01"), "Decision Overdue")

	def test_permanent_contract_does_not_expire_at_probation_end(self):
		doc = SimpleNamespace(
			contract_type="Permanent",
			end_date=None,
			probation_end_date="2026-06-30",
		)
		self.assertIsNone(get_effective_end_date(doc))

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

	def test_expired_fixed_term_contract_can_be_renewed(self):
		doc = self._contract("2025-01-01", "2025-12-31", status="Expired")
		self.assertEqual(get_allowed_successor_actions(doc), ["Renewal"])
		self.assertEqual(
			validate_successor_transition(doc, "Renewal", "2026-01-01", "Fixed Term"),
			"Fixed Term",
		)

	def test_active_fixed_term_contract_can_be_extended(self):
		doc = self._contract("2026-01-01", "2026-12-31")
		self.assertIn("Extension", get_allowed_successor_actions(doc))
		self.assertEqual(
			validate_successor_transition(doc, "Extension", "2027-01-01", "Fixed Term"),
			"Fixed Term",
		)

	def test_open_probation_blocks_normal_contract_actions(self):
		doc = self._contract(
			"2026-01-01",
			"2028-12-31",
			has_probation=1,
			probation_status="Under Probation",
		)
		self.assertEqual(get_allowed_successor_actions(doc), ["Amendment"])
		self.assertEqual(
			validate_successor_transition(doc, "Amendment", "2026-10-26", "Fixed Term"),
			"Fixed Term",
		)
		with self.assertRaises(frappe.ValidationError):
			validate_successor_transition(doc, "Extension", "2029-01-01", "Fixed Term")

	def test_probation_decisions_open_on_review_date(self):
		doc = SimpleNamespace(probation_review_date="2026-05-31")
		self.assertFalse(is_probation_review_window_open(doc, "2026-05-30"))
		self.assertTrue(is_probation_review_window_open(doc, "2026-05-31"))

	def test_scheduled_probation_contract_can_only_be_amended(self):
		doc = self._contract(
			"2027-01-01",
			"2029-12-31",
			status="Scheduled",
			has_probation=1,
			probation_status="Pending",
		)
		self.assertEqual(get_allowed_successor_actions(doc), ["Amendment"])

	def test_extension_cannot_overlap_current_contract(self):
		doc = self._contract("2026-01-01", "2026-12-31")
		with self.assertRaises(frappe.ValidationError):
			validate_successor_transition(doc, "Extension", "2026-12-31", "Fixed Term")

	def test_expired_contract_cannot_be_extended(self):
		doc = self._contract("2025-01-01", "2025-12-31", status="Expired")
		with self.assertRaises(frappe.ValidationError):
			validate_successor_transition(doc, "Extension", "2026-01-01", "Fixed Term")

	@staticmethod
	def _contract(
		start_date,
		end_date,
		status="Active",
		has_probation=0,
		probation_status=None,
	):
		return type(
			"ContractStub",
			(),
			{
				"docstatus": 1,
				"contract_type": "Fixed Term",
				"has_probation": has_probation,
				"probation_status": probation_status,
				"probation_review_date": "2026-05-31" if has_probation else None,
				"start_date": start_date,
				"end_date": end_date,
				"probation_end_date": None,
				"status": status,
			},
		)()
