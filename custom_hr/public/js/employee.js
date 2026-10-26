frappe.ui.form.on("Employee", {
	refresh(frm) {
		if (frm.is_new()) return;
		frappe.call({
			method: "custom_hr.contract_management.api.get_contract_context",
			args: { employee: frm.doc.name },
			callback(r) {
				const context = r.message || {};
				if (context.current) {
					frm.add_custom_button(__("View Current Contract"), () => {
						frappe.set_route("Form", "Employee Contract", context.current.name);
					}, __("Contract"));
					frm.add_custom_button(__("Contract History"), () => {
						frappe.set_route("List", "Employee Contract", { employee: frm.doc.name });
					}, __("Contract"));
					if (context.can_manage) {
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
				} else if (context.can_manage) {
					frm.add_custom_button(__("Create Contract"), () => {
						const dialog = new frappe.ui.Dialog({
							title: __("Create Employee Contract"),
							fields: [
								{ fieldname: "contract_type", fieldtype: "Select", label: __("Contract Type"), options: "Probationary\nFixed Term\nPermanent", reqd: 1 },
								{ fieldname: "start_date", fieldtype: "Date", label: __("Start Date"), default: frm.doc.date_of_joining || frappe.datetime.get_today(), reqd: 1 },
								{ fieldname: "contract_duration_months", fieldtype: "Int", label: __("Contract Duration (Months)"), depends_on: "eval:doc.contract_type!='Permanent'", mandatory_depends_on: "eval:doc.contract_type!='Permanent'" },
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
