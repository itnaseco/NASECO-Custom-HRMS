import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def install_employee_custom_fields():
	"""Install the read-only Employee contract summary maintained by this app."""
	create_custom_fields(
		{
			"Employee": [
				{
					"fieldname": "custom_contract_details_section",
					"fieldtype": "Section Break",
					"label": "Contract Details",
					"insert_after": "employment_details",
					"collapsible": 1,
				},
				{
					"fieldname": "custom_current_contract",
					"fieldtype": "Link",
					"label": "Current Contract",
					"options": "Employee Contract",
					"insert_after": "custom_contract_details_section",
					"read_only": 1,
				},
				{
					"fieldname": "custom_contract_type",
					"fieldtype": "Data",
					"label": "Contract Type",
					"insert_after": "custom_current_contract",
					"read_only": 1,
				},
				{
					"fieldname": "custom_contract_duration_months",
					"fieldtype": "Int",
					"label": "Contract Duration (Months)",
					"insert_after": "custom_contract_type",
					"read_only": 1,
				},
				{
					"fieldname": "custom_contract_start_date",
					"fieldtype": "Date",
					"label": "Contract Start Date",
					"insert_after": "custom_contract_duration_months",
					"read_only": 1,
				},
				{
					"fieldname": "custom_contract_end_date",
					"fieldtype": "Date",
					"label": "Contract End Date",
					"insert_after": "custom_contract_start_date",
					"read_only": 1,
				},
				{
					"fieldname": "custom_contract_details_column",
					"fieldtype": "Column Break",
					"insert_after": "custom_contract_end_date",
				},
				{
					"fieldname": "custom_probation_end_date",
					"fieldtype": "Date",
					"label": "Probation End Date",
					"insert_after": "custom_contract_details_column",
					"read_only": 1,
				},
				{
					"fieldname": "custom_contract_status",
					"fieldtype": "Data",
					"label": "Contract Status",
					"insert_after": "custom_probation_end_date",
					"read_only": 1,
				},
				{
					"fieldname": "custom_next_contract_review_date",
					"fieldtype": "Date",
					"label": "Next Contract Review Date",
					"insert_after": "custom_contract_status",
					"read_only": 1,
				},
				{
					"fieldname": "custom_projected_retirement_date",
					"fieldtype": "Date",
					"label": "Projected Retirement Date",
					"insert_after": "custom_next_contract_review_date",
					"read_only": 1,
				},
			],
		},
		update=True,
	)
	frappe.clear_cache(doctype="Employee")
