frappe.ui.form.on("Contract Probation Action", {
	refresh(frm) {
		if (frm.is_new() && frm.doc.contract) {
			frm.trigger("contract");
		}
	},
	contract(frm) {
		if (!frm.doc.contract) return;
		frappe.db.get_value(
			"Employee Contract",
			frm.doc.contract,
			["probation_end_date"],
		).then((r) => {
			frm.set_value("previous_probation_end_date", r.message.probation_end_date);
			frm.trigger("extension_duration_months");
		});
	},
	extension_duration_months(frm) {
		if (!frm.doc.previous_probation_end_date || !frm.doc.extension_duration_months) return;
		frm.set_value(
			"revised_probation_end_date",
			frappe.datetime.add_months(frm.doc.previous_probation_end_date, frm.doc.extension_duration_months),
		);
	},
});
