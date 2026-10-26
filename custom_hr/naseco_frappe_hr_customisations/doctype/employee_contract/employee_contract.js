frappe.ui.form.on("Employee Contract", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1 || !["Scheduled", "Active", "Expiring"].includes(frm.doc.status)) return;

		frm.add_custom_button(__("Renew / Extend"), () => {
			const dialog = new frappe.ui.Dialog({
				title: __("Create Successor Contract"),
				fields: [
					{ fieldname: "change_type", fieldtype: "Select", label: __("Change Type"), options: "Renewal\nExtension\nConfirmation\nAmendment", reqd: 1 },
					{ fieldname: "contract_type", fieldtype: "Select", label: __("Contract Type"), options: "Probationary\nFixed Term\nPermanent", default: frm.doc.contract_type, reqd: 1 },
					{ fieldname: "start_date", fieldtype: "Date", label: __("Start Date"), reqd: 1 },
					{ fieldname: "end_date", fieldtype: "Date", label: __("End Date") },
				],
				primary_action_label: __("Create Draft"),
				primary_action(values) {
					frm.call("make_successor", values).then((r) => {
						dialog.hide();
						frappe.set_route("Form", "Employee Contract", r.message);
					});
				},
			});
			dialog.show();
		}, __("Contract"));

		frm.add_custom_button(__("Terminate"), () => {
			const dialog = new frappe.ui.Dialog({
				title: __("Terminate Contract"),
				fields: [
					{ fieldname: "category", fieldtype: "Select", label: __("Category"), options: "Expiry / Non-renewal\nResignation\nRetirement\nMisconduct Dismissal\nPoor-performance Dismissal\nRedundancy\nIncapacity / Sickness\nMutual Separation\nDeath", reqd: 1 },
					{ fieldname: "termination_date", fieldtype: "Date", label: __("Effective Date"), default: frappe.datetime.get_today(), reqd: 1 },
					{ fieldname: "reason", fieldtype: "Small Text", label: __("Reason"), reqd: 1 },
				],
				primary_action_label: __("Confirm Termination"),
				primary_action(values) {
					frappe.confirm(__("Terminate this contract? This action will be recorded in its history."), () => {
						frm.call("terminate", values).then(() => {
							dialog.hide();
							frm.reload_doc();
						});
					});
				},
			});
			dialog.show();
		}, __("Contract"));
	},
});
