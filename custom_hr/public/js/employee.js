function create_employee_probation_action(contract, action_type) {
	frappe.new_doc("Contract Probation Action", {
		contract,
		action_type,
		decision_date: frappe.datetime.get_today(),
		effective_date: frappe.datetime.get_today(),
	});
}

function amend_employee_contract(contract) {
	const fields = [
		{
			fieldname: "start_date",
			fieldtype: "Date",
			label: __("Amendment Effective Date"),
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
	];
	if (contract.contract_type !== "Permanent") {
		fields.push({
			fieldname: "duration_months",
			fieldtype: "Int",
			label: __("Contract Duration (Months)"),
			default: contract.contract_duration_months,
			reqd: 1,
		});
	}
	const dialog = new frappe.ui.Dialog({
		title: __("Amend Contract"),
		fields,
		primary_action_label: __("Create Amendment Draft"),
		primary_action(values) {
			frappe.call({
				method: "custom_hr.contract_management.api.create_contract_amendment",
				type: "POST",
				args: { contract: contract.name, ...values },
				callback(result) {
					dialog.hide();
					if (result.message) frappe.set_route("Form", "Employee Contract", result.message);
				},
			});
		},
	});
	dialog.show();
}

function add_employee_probation_actions(frm, context) {
	const contract = context.current;
	if (!contract || !(contract.has_probation || contract.contract_type === "Probationary")) return;

	const group = __("Probation Actions");
	frm.add_custom_button(__("View Probation Details"), () => {
		custom_hr.probation_dialogs.show_details(contract.name);
	}, group);
	frm.add_custom_button(__("Probation History"), () => {
		custom_hr.probation_dialogs.show_history(contract.name);
	}, group);

	const open_statuses = ["Pending", "Under Probation", "Evaluation Due", "Extended", "Decision Overdue"];
	const probation_is_open =
		["Active", "Expiring"].includes(contract.status) &&
		open_statuses.includes(contract.probation_status || "Under Probation");
	if (!context.can_manage || !probation_is_open) return;

	frm.add_custom_button(__("Amend Contract"), () => {
		amend_employee_contract(contract);
	}, __("Contract"));
	frm.add_custom_button(__("Terminate During Probation"), () => {
		create_employee_probation_action(contract.name, "Termination");
	}, group);

	const review_window_open =
		contract.probation_review_date &&
		frappe.datetime.get_diff(frappe.datetime.get_today(), contract.probation_review_date) >= 0;
	if (review_window_open) {
		frm.add_custom_button(__("Confirm Employee"), () => {
			create_employee_probation_action(contract.name, "Confirmation");
		}, group);
		frm.add_custom_button(__("Extend Probation"), () => {
			create_employee_probation_action(contract.name, "Extension");
		}, group);
	}
}

frappe.ui.form.on("Employee", {
	refresh(frm) {
		if (frm.is_new()) return;
		frappe.call({
			method: "custom_hr.contract_management.api.get_contract_context",
			args: { employee: frm.doc.name },
			callback(r) {
				const context = r.message || {};
				add_employee_probation_actions(frm, context);
				if (context.has_contract_history) {
					frm.add_custom_button(__("Contract History"), () => {
						custom_hr.contract_dialogs.show_history(frm.doc.name);
					}, __("Contract"));
				}
				if (context.current) {
					frm.add_custom_button(__("View Current Contract"), () => {
						custom_hr.contract_dialogs.show_details(context.current.name);
					}, __("Contract"));
					if (context.can_manage && context.current.status !== "Pending Termination") {
						frm.add_custom_button(__("Start Review"), () => {
							frappe.call({
								method: "custom_hr.contract_management.api.start_contract_review",
								type: "POST",
								args: { contract: context.current.name },
								callback(result) {
									if (result.message) frappe.set_route("Form", "Contract Review", result.message);
								},
							});
						}, __("Contract"));
					}
				} else if (
					context.can_manage &&
					!context.has_contract_history &&
					frm.doc.status !== "Left"
				) {
					frm.add_custom_button(__("Create Contract"), () => {
						const dialog = new frappe.ui.Dialog({
							title: __("Create Employee Contract"),
							fields: [
								{ fieldname: "contract_type", fieldtype: "Select", label: __("Contract Type"), options: "Fixed Term\nPermanent", reqd: 1 },
								{ fieldname: "start_date", fieldtype: "Date", label: __("Start Date"), default: frm.doc.date_of_joining || frappe.datetime.get_today(), reqd: 1 },
								{ fieldname: "contract_duration_months", fieldtype: "Int", label: __("Contract Duration (Months)"), depends_on: "eval:doc.contract_type!='Permanent'", mandatory_depends_on: "eval:doc.contract_type!='Permanent'" },
								{ fieldname: "has_probation", fieldtype: "Check", label: __("Employee Will Serve Probation"), default: 1 },
								{ fieldname: "probation_duration_months", fieldtype: "Int", label: __("Probation Period (Months)"), default: 6, depends_on: "eval:doc.has_probation", mandatory_depends_on: "eval:doc.has_probation" },
							],
							primary_action_label: __("Create Draft"),
							primary_action(values) {
								frappe.call({
									method: "custom_hr.contract_management.api.create_contract",
									type: "POST",
									args: { employee: frm.doc.name, ...values },
									callback(result) {
										dialog.hide();
										if (result.message) frappe.set_route("Form", "Employee Contract", result.message);
									},
								});
							},
						});
						dialog.show();
					}, __("Contract"));
				}
			},
		});
	},
});
