frappe.provide("custom_hr.probation_dialogs");
frappe.provide("custom_hr.contract_dialogs");

(() => {
	const escape = (value) => frappe.utils.escape_html(String(value ?? ""));
	const display = (value) => (value === null || value === undefined || value === "" ? __("Not set") : escape(value));
	const date = (value) => (value ? escape(frappe.datetime.str_to_user(value)) : __("Not set"));
	const link = (url, label) => {
		if (!url) return `<span class="text-muted">${__("Not attached")}</span>`;
		return `<a href="${escape(encodeURI(url))}" target="_blank" rel="noopener noreferrer">${escape(label)}</a>`;
	};
	const row = (label, value) => `
		<div class="d-flex justify-content-between border-bottom py-2" style="gap: 1rem;">
			<span class="text-muted">${escape(label)}</span><span class="text-right">${value}</span>
		</div>`;
	const document_status = (docstatus) => {
		if (docstatus === 1) return `<span class="indicator-pill green">${__("Submitted")}</span>`;
		if (docstatus === 2) return `<span class="indicator-pill red">${__("Cancelled")}</span>`;
		return `<span class="indicator-pill orange">${__("Draft")}</span>`;
	};

	function remaining_label(days) {
		if (days === null || days === undefined) return __("Not available");
		if (days < 0) return __("{0} day(s) overdue", [Math.abs(days)]);
		if (days === 0) return __("Ends today");
		return __("{0} day(s) remaining", [days]);
	}

	function details_html(data) {
		const contract = data.contract;
		const latest = data.history[0];
		return `
			<div class="mb-3">
				<h5>${escape(contract.employee_name || contract.employee)}</h5>
				<div class="text-muted">${escape(contract.employee)} · ${escape(contract.company)}</div>
			</div>
			<div class="row">
				<div class="col-md-6">
					${row(__("Contract"), display(contract.name))}
					${row(__("Contract Type"), display(contract.contract_type))}
					${row(__("Contract Status"), display(contract.contract_status))}
					${row(__("Contract Period"), `${date(contract.start_date)} – ${date(contract.end_date)}`)}
					${row(__("Probation Status"), display(contract.probation_status))}
				</div>
				<div class="col-md-6">
					${row(__("Probation Period"), `${date(contract.probation_start_date)} – ${date(contract.probation_end_date)}`)}
					${row(__("Initial Duration"), contract.probation_duration_months ? __("{0} month(s)", [contract.probation_duration_months]) : __("Not set"))}
					${row(__("Original End Date"), date(contract.original_probation_end_date))}
					${row(__("Evaluation Due"), date(contract.probation_review_date))}
					${row(__("Time Remaining"), escape(remaining_label(data.days_remaining)))}
					${row(__("Confirmation Date"), date(contract.confirmation_date))}
				</div>
			</div>
			<div class="mt-3">
				${row(__("Probation Contract"), link(contract.probation_contract_document, __("Open attachment")))}
				${row(__("Latest Evaluation"), latest ? display(latest.evaluation_result) : __("No decision recorded"))}
			</div>`;
	}

	function history_html(data) {
		if (!data.history.length) {
			return `<div class="text-center text-muted py-5">${__("No probation decisions have been recorded for this contract.")}</div>`;
		}
		return data.history.map((item) => `
			<div class="card mb-3">
				<div class="card-body">
					<div class="d-flex justify-content-between align-items-start mb-2" style="gap: 1rem;">
						<div><strong>${display(item.action_type)}</strong><div class="text-muted small">${date(item.decision_date)}</div></div>
						<span class="indicator-pill ${item.docstatus === 1 ? "green" : item.docstatus === 2 ? "red" : "orange"}">${item.docstatus === 1 ? __("Submitted") : item.docstatus === 2 ? __("Cancelled") : __("Draft")}</span>
					</div>
					${row(__("Effective Date"), date(item.effective_date))}
					${row(__("Evaluation Result"), display(item.evaluation_result))}
					${row(__("Decision Reason"), display(item.reason))}
					${item.action_type === "Extension" ? row(__("Probation End Date"), `${date(item.previous_probation_end_date)} → ${date(item.revised_probation_end_date)}`) : ""}
					${item.action_type === "Extension" ? row(__("Employee Agreement Date"), date(item.employee_agreement_date)) : ""}
					${row(__("Documents"), [
						link(item.evaluation_document, __("Evaluation")),
						link(item.decision_document, __("Decision letter")),
						link(item.employee_agreement_document, __("Agreement")),
					].join(" · "))}
					${item.approval_notes ? row(__("Approval Notes"), display(item.approval_notes)) : ""}
					<div class="text-muted small mt-2">${__("Recorded by {0}", [escape(item.owner)])}</div>
				</div>
			</div>`).join("");
	}

	function show(contract, view) {
		frappe.call({
			method: "custom_hr.contract_management.api.get_probation_overview",
			args: { contract },
			freeze: true,
			freeze_message: __("Loading probation information..."),
			callback(result) {
				if (!result.message) return;
				const data = result.message;
				const dialog = new frappe.ui.Dialog({
					title: view === "history" ? __("Probation History") : __("Probation Details"),
					size: "large",
					fields: [{ fieldname: "content", fieldtype: "HTML" }],
					primary_action_label: __("Close"),
					primary_action: () => dialog.hide(),
				});
				dialog.fields_dict.content.$wrapper.html(view === "history" ? history_html(data) : details_html(data));
				dialog.add_custom_action(__("Open Full Contract"), () => {
					dialog.hide();
					frappe.set_route("Form", "Employee Contract", data.contract.name);
				});
				if (view === "history") {
					dialog.add_custom_action(__("Open History List"), () => {
						dialog.hide();
						frappe.set_route("List", "Contract Probation Action", { contract: data.contract.name });
					});
				}
				dialog.show();
			},
		});
	}

	function contract_details_html(contract) {
		const has_probation = contract.has_probation || contract.contract_type === "Probationary";
		const terminated = contract.termination_date || contract.status === "Terminated";
		return `
			<div class="mb-3 d-flex justify-content-between align-items-start" style="gap: 1rem;">
				<div><h5>${escape(contract.employee_name || contract.employee)}</h5><div class="text-muted">${escape(contract.employee)} · ${escape(contract.company)}</div></div>
				${document_status(contract.docstatus)}
			</div>
			<div class="row">
				<div class="col-md-6">
					${row(__("Contract"), display(contract.name))}
					${row(__("Contract Type"), display(contract.contract_type))}
					${row(__("Change Type"), display(contract.change_type))}
					${row(__("Status"), display(contract.status))}
					${row(__("Contract Period"), `${date(contract.start_date)} – ${date(contract.end_date)}`)}
					${row(__("Duration"), contract.contract_duration_months ? escape(__("{0} month(s)", [contract.contract_duration_months])) : __("Not applicable"))}
				</div>
				<div class="col-md-6">
					${row(__("Designation"), display(contract.designation))}
					${row(__("Department"), display(contract.department))}
					${row(__("Branch"), display(contract.branch))}
					${row(__("Work Location"), display(contract.work_location))}
					${row(__("Next Review Date"), date(contract.next_review_date))}
					${row(__("Previous Contract"), display(contract.previous_contract))}
				</div>
			</div>
			<div class="mt-3">
				${has_probation ? row(__("Probation"), `${display(contract.probation_status)} · ${__("ends")} ${date(contract.probation_end_date)}`) : ""}
				${row(__("Employee Acceptance Date"), date(contract.employee_acceptance_date))}
				${row(__("Signed Contract"), link(contract.signed_contract, __("Open signed contract")))}
			</div>
			${terminated ? `<div class="mt-3"><h6>${__("Termination")}</h6>
				${row(__("Category"), display(contract.termination_category))}
				${row(__("Effective Date"), date(contract.termination_date))}
				${row(__("Reason"), display(contract.termination_reason))}
				${row(__("Supporting Document"), link(contract.termination_document, __("Open attachment")))}
			</div>` : ""}`;
	}

	function contract_history_html(contracts) {
		if (!contracts.length) {
			return `<div class="text-center text-muted py-5">${__("No contracts have been recorded for this employee.")}</div>`;
		}
		return contracts.map((contract) => `
			<div class="card mb-3">
				<div class="card-body">
					<div class="d-flex justify-content-between align-items-start mb-2" style="gap: 1rem;">
						<div><strong>${display(contract.contract_type)}</strong><div class="text-muted small">${date(contract.start_date)} – ${date(contract.end_date)}</div></div>
						<div class="text-right"><span class="indicator-pill ${["Active", "Expiring"].includes(contract.status) ? "green" : contract.status === "Terminated" ? "red" : "gray"}">${display(contract.status)}</span></div>
					</div>
					${row(__("Contract"), `<a href="/app/employee-contract/${encodeURIComponent(contract.name)}">${escape(contract.name)}</a>`)}
					${row(__("Change Type"), display(contract.change_type))}
					${row(__("Previous Contract"), display(contract.previous_contract))}
					${row(__("Duration"), contract.contract_duration_months ? escape(__("{0} month(s)", [contract.contract_duration_months])) : __("Not applicable"))}
					${contract.has_probation || contract.contract_type === "Probationary" ? row(__("Probation Status"), display(contract.probation_status)) : ""}
					${contract.termination_date ? row(__("Termination"), `${date(contract.termination_date)} · ${display(contract.termination_category)}`) : ""}
					${row(__("Signed Contract"), link(contract.signed_contract, __("Open attachment")))}
				</div>
			</div>`).join("");
	}

	function show_contract_details(contract) {
		frappe.call({
			method: "custom_hr.contract_management.api.get_contract_overview",
			args: { contract },
			freeze: true,
			freeze_message: __("Loading contract information..."),
			callback(result) {
				if (!result.message) return;
				const data = result.message;
				const dialog = new frappe.ui.Dialog({
					title: __("Current Contract"), size: "large",
					fields: [{ fieldname: "content", fieldtype: "HTML" }],
					primary_action_label: __("Close"), primary_action: () => dialog.hide(),
				});
				dialog.fields_dict.content.$wrapper.html(contract_details_html(data));
				dialog.add_custom_action(__("Open Full Contract"), () => {
					dialog.hide();
					frappe.set_route("Form", "Employee Contract", data.name);
				});
				dialog.show();
			},
		});
	}

	function show_contract_history(employee) {
		frappe.call({
			method: "custom_hr.contract_management.api.get_employee_contract_history",
			args: { employee },
			freeze: true,
			freeze_message: __("Loading contract history..."),
			callback(result) {
				const contracts = result.message || [];
				const dialog = new frappe.ui.Dialog({
					title: __("Contract History"), size: "large",
					fields: [{ fieldname: "content", fieldtype: "HTML" }],
					primary_action_label: __("Close"), primary_action: () => dialog.hide(),
				});
				dialog.fields_dict.content.$wrapper.html(contract_history_html(contracts));
				dialog.add_custom_action(__("Open History List"), () => {
					dialog.hide();
					frappe.set_route("List", "Employee Contract", { employee });
				});
				dialog.show();
			},
		});
	}

	custom_hr.probation_dialogs.show_details = (contract) => show(contract, "details");
	custom_hr.probation_dialogs.show_history = (contract) => show(contract, "history");
	custom_hr.contract_dialogs.show_details = show_contract_details;
	custom_hr.contract_dialogs.show_history = show_contract_history;
})();
