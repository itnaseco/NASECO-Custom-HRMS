frappe.listview_settings["Employee Contract"] = {
	get_indicator(doc) {
		const colours = { Active: "green", Expiring: "orange", "Pending Termination": "orange", Expired: "red", Terminated: "red", Scheduled: "blue", Superseded: "gray" };
		return [__(doc.status), colours[doc.status] || "gray", `status,=,${doc.status}`];
	},
};
