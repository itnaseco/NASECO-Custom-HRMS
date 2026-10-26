function successor_start_date(frm, change_type) {
	if (["Renewal", "Extension", "Confirmation"].includes(change_type)) {
		const end_date = frm.doc.end_date || frm.doc.probation_end_date;
		if (end_date) return frappe.datetime.add_days(end_date, 1);
	}
	return frm.doc.status === "Scheduled" ? frm.doc.start_date : frappe.datetime.get_today();
}

function successor_contract_type(frm, change_type) {
	if (change_type === "Confirmation") return "Permanent";
	return frm.doc.contract_type;
}

function show_successor_dialog(frm, change_type) {
	const labels = {
		Renewal: __("Renew Contract"),
		Extension: __("Extend Contract"),
		Confirmation: __("Confirm Employee"),
		Amendment: __("Amend Contract"),
	};
	const lock_contract_type = ["Renewal", "Extension", "Amendment"].includes(change_type);
	const dialog = new frappe.ui.Dialog({
		title: labels[change_type],
		fields: [
			{ fieldname: "change_type", fieldtype: "Data", hidden: 1, default: change_type },
			{
				fieldname: "contract_type",
				fieldtype: "Select",
				label: __("New Contract Type"),
				options: change_type === "Confirmation" ? "Fixed Term\nPermanent" : "Probationary\nFixed Term\nPermanent",
				default: successor_contract_type(frm, change_type),
				read_only: lock_contract_type,
				reqd: 1,
			},
			{
				fieldname: "start_date",
				fieldtype: "Date",
				label: __("Effective Start Date"),
				default: successor_start_date(frm, change_type),
				reqd: 1,
			},
			{
				fieldname: "duration_months",
				fieldtype: "Int",
				label: __("Contract Duration (Months)"),
				default: frm.doc.contract_duration_months,
				depends_on: "eval:doc.contract_type!='Permanent'",
				mandatory_depends_on: "eval:doc.contract_type!='Permanent'",
			},
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
}

frappe.ui.form.on("Employee Contract", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;

		const status = frm.doc.status;
		const type = frm.doc.contract_type;
		if (status === "Expired" && type === "Fixed Term") {
			frm.add_custom_button(__("Renew Contract"), () => show_successor_dialog(frm, "Renewal"), __("Contract"));
		}
		if (["Active", "Expiring"].includes(status)) {
			if (["Fixed Term", "Probationary"].includes(type)) {
				frm.add_custom_button(__("Extend Contract"), () => show_successor_dialog(frm, "Extension"), __("Contract"));
			}
			if (type === "Fixed Term") {
				frm.add_custom_button(__("Renew Contract"), () => show_successor_dialog(frm, "Renewal"), __("Contract"));
			}
			if (type === "Probationary") {
				frm.add_custom_button(__("Confirm Employee"), () => show_successor_dialog(frm, "Confirmation"), __("Contract"));
			}
			frm.add_custom_button(__("Amend Contract"), () => show_successor_dialog(frm, "Amendment"), __("Contract"));
		}
		if (status === "Scheduled") {
			frm.add_custom_button(__("Amend Contract"), () => show_successor_dialog(frm, "Amendment"), __("Contract"));
		}

		if (!["Scheduled", "Active", "Expiring"].includes(status)) return;
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
