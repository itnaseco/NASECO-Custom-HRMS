# Employee Contract Management: Minimal Implementation Workplan

## 1. Scope and design rules

Deliver a small, auditable contract lifecycle inside `custom_hr`.

- `Employee Contract` is the source of truth.
- Employee contract fields are read-only summaries of the active contract.
- A submitted contract is not edited in place; renewal, extension, or a material change creates a linked successor contract.
- Only one contract may be active for an employee on a given date.
- Expiry, non-renewal, resignation, retirement, and dismissal remain distinct outcomes.
- The first release covers Probationary, Fixed Term, and Permanent contracts only.

Out of scope for the first release: contract-template authoring, electronic signatures, payroll calculations, bulk renewal, employee self-service, and a full disciplinary case-management module.

## 2. Deliverables

### A. Employee Contract DocType

Create a submittable DocType with:

- employee, employee name, company, contract number
- contract type: Probationary, Fixed Term, Permanent
- start date, end date, probation end date
- status: Draft, Scheduled, Active, Expiring, Expired, Superseded, Terminated
- previous contract and change type: New, Renewal, Extension, Confirmation, Amendment
- job title, department, branch, grade, reports to, work location
- wage, currency, pay frequency, normal working hours
- leave entitlement and notice period
- retirement age and projected retirement date for permanent contracts
- signed contract attachment, employee acceptance date, approval details
- termination category, date, reason, and supporting document

Core validations:

- Probationary contracts must be written records, last no more than six months initially, and occur only once per continuous employment.
- A probation extension requires employee agreement and may not exceed a further six months.
- Fixed Term requires an end date later than its start date.
- Permanent must not have a contractual end date.
- Contract periods must not overlap, except a future successor may be prepared before activation.
- Only HR-authorised users may submit, terminate, or supersede contracts.

### B. Contract Review DocType

Create a lightweight review record linked to the expiring contract:

- employee, contract, due date, interview date
- manager recommendation and HR recommendation
- decision: Pending, Renew, Extend, Confirm, Convert to Permanent, Do Not Renew
- proposed start/end dates and notes
- review status and approvers

Allow one open review per contract. Keep sensitive review notes permission-restricted.

### C. Employee integration

Add custom fields through fixtures:

- current contract
- contract type
- contract start date
- contract end date
- probation end date
- contract status
- next contract review date
- projected retirement date

Make the fields read-only and update them only through server-side contract lifecycle services.

Add Employee form actions:

- View Current Contract
- View Contract History
- Create/Renew Contract
- Start Contract Review
- Terminate Contract

Each mutating action must show a confirmation and then call a permission-checked server method. Termination must capture category, effective date, reason, and approval rather than immediately disabling the Employee.

### D. Lifecycle service

Keep lifecycle rules in a small service module used by DocType controllers and whitelisted actions:

- activate a scheduled contract
- create a successor for renewal, extension, confirmation, or amendment
- supersede the previous contract when its successor becomes active
- terminate a contract with a recorded reason
- expire due contracts
- synchronise the Employee summary

Use database locking or an equivalent transactional check during activation to prevent two active contracts.

### E. Notifications and review creation

Register one daily scheduler task.

- Create the Contract Review at 60 days before expiry if none exists.
- Notify HR Manager and the employee's reports-to manager at 60 and 30 days.
- Escalate unresolved reviews at 14 and 7 days.
- Flag overdue contracts where the Employee remains active after expiry.
- Apply the same escalation to probation ending without a confirmation, agreed extension, or termination decision.

Store notification milestones on the contract/review so the task is idempotent. Put lead times in a singleton `Contract Management Settings` DocType rather than hard-coding them.

### F. Roles and permissions

- HR User: read and prepare drafts/reviews.
- HR Manager: submit, activate, renew, supersede, and terminate.
- Reporting Manager: read assigned reviews and record a recommendation; no wage access.
- Employee: no access in the first release.
- System Manager: configuration and emergency administration.

Signed files must be private. Salary and sensitive review fields require stricter field or document access than general contract dates.

## 3. Implementation sequence

1. **Foundation** — declare `frappe` and `hrms` as required apps, create the settings and two DocTypes, roles/permissions, and fixtures.
2. **Rules** — implement date, type, overlap, probation, transition, and permission validations.
3. **Lifecycle** — implement activation, successor creation, termination, expiry, and Employee synchronisation.
4. **User interface** — add Employee buttons, dialogs, list indicators, filters, and contract dashboard links.
5. **Automation** — add daily review creation, reminders, escalation, and expiry processing.
6. **Verification and rollout** — automate tests, migrate a staging site, import current contracts, reconcile Employees, train HR, then enable the scheduler in production.

## 4. Minimum test matrix

- Each contract type accepts valid dates and rejects invalid dates.
- Permanent contracts reject an end date.
- Initial and extended probation limits are enforced, including employee agreement.
- A second probationary engagement and overlapping active contracts are rejected.
- Renewal produces a linked successor and preserves the original submitted record.
- Activation and termination update the Employee summary correctly.
- Users without HR Manager rights cannot activate, supersede, or terminate.
- The daily task creates only one review and sends each reminder milestone once.
- Expired and unresolved probation contracts are escalated without silently disabling the Employee.
- Concurrent activation attempts cannot produce two active contracts.

## 5. Definition of done

- All DocTypes, custom fields, permissions, hooks, and settings are exported with the app and install cleanly on a fresh test site.
- Existing active contracts are imported and reconciled with every active Employee.
- Automated controller, permission, lifecycle, and scheduler tests pass.
- HR validates the workflows and generated audit trail in staging.
- A Ugandan employment-law reviewer approves the configured wording, probation rules, retirement policy, notice handling, and termination categories before production use.

## 6. Suggested app layout

```text
custom_hr/
  hooks.py
  fixtures/
  contract_management/
    services.py
    scheduled_tasks.py
  naseco_frappe_hr_customisations/doctype/
    contract_management_settings/
    employee_contract/
    contract_review/
  public/js/
    employee.js
```

Keep legal and organisational policy values configurable. Code should enforce the approved configuration and preserve evidence; it should not attempt to decide whether a particular dismissal or non-renewal is legally justified.
