# Vault configuration promotion, drift and rotation reporting

**Status: built and tested with disposable Vaults; ready for a customer pilot. Customer DEV/UAT/PROD have not been configured or deployed.**

Git holds intended configuration and secret structure. Vault holds each environment's own secret values. Security keeps UI access and uses **GitHub Actions to run Terraform Community CLI** for configuration promotion. No Terraform shell wrapper or CLI training is required for Security.

## What has been delivered

| Deliverable | Built behavior |
| --- | --- |
| Workstream 1: configuration promotion | Reviewed Git release references; per-environment Terraform plan; protected-environment approval before applying the saved plan. Current Terraform scope is one application's ACL policy and AppRole. |
| Initial secret entry | Guided script uses Git-defined path/keys, prompts without echo and writes directly to the target Vault. Create-only writes refuse existing and soft-deleted paths. Existing locations need no recreation. |
| Workstream 2: inventory and drift | Inventory ACL/password policies, all enabled auth/engine mounts and supported configurations, including LDAP mappings. Compare DEV/UAT/PROD and the selected application's Git baseline. |
| KV v2 structure | Discover all accessible KV v2 mounts and recursively scan metadata paths and nested keys through [Read Secret Subkeys](https://developer.hashicorp.com/vault/api-docs/secret/kv/kv-v2#read-secret-subkeys), without reading KV values. |
| Rotation ages | Dedicated `rotation-report.py` reports current, overdue, missing, invalid and future dates from operator-maintained metadata. It does not rotate credentials. |
| GitHub automation | Validation, disposable OIDC pilot, manual promotion, and daily/on-demand inventory workflows. Daily reporting saves `comparison.json` and `rotation-report.json`. |

Application values never enter Git, GitHub secrets or the default Terraform plan/state. Reads and value edits remain in the Vault UI. Reports make no corrections or deletions. Unsupported plugin details and denied/failed reads are explicit; incomplete evidence cannot pass as equal. See [exact coverage and exclusions](INVENTORY.md).

## What has been tested

| Evidence | Verified result |
| --- | --- |
| [Validation workflow: 21 tests passed](https://github.com/tekanaid-user/vault-in-vmware/actions/runs/37376406133) | Multiple/empty/nested KV mounts, policies, supported adapters, drift in every inventory category, rotation dates, create-only writes and permission failures. Terraform imports, saved-plan apply, subsequent no-change plan, and absence of synthetic application values/tokens from state. |
| [Real GitHub OIDC pilot: passed](https://github.com/tekanaid-user/vault-in-vmware/actions/runs/37376409400) | Three disposable TLS Vaults; actual GitHub-issued JWTs; scoped identities; rejected untrusted repository binding; complete baseline parity and detected UAT drift. |
| Keys-only access | API and Vault CLI expose keys through subkeys; restricted identities receive HTTP 403 when attempting to read KV values. UI behavior remains unverified. |
| Tool/workflow validation | Vault 2.1.0, Terraform CLI 1.16.1, Vault provider 5.8.0. Both Terraform roots validated; workflow, shell and CLI checks passed. Database/Sentinel adapters used API fixtures rather than live Enterprise/database infrastructure. |

These results cover synthetic Vaults, not customer infrastructure, remote state or customer deployments. Interactive secret entry with Security's own identity remains a pilot check. [Full evidence and limits](VALIDATION.md).

## Customer setup and acceptance

Start with **read-only inventory**, then promote **one agreed application**. Drift reporting does not require Terraform state.

| Step | Owner | Needed before live use |
| --- | --- | --- |
| 1. Scope and baseline | Security + implementation lead | Confirm Vault versions, namespaces/mounts, pilot application, policy/AppRole settings and intended environment differences. Review supported adapter coverage and exact permissions for nested mounts. |
| 2. GitHub controls | Customer repository administrator | Use an approved repository/report access model, protect `main`, set reviewers and restrict deployment environments. This public repository is a generic example; customer addresses and inventory belong in approved locations. |
| 3. Connectivity and runner | DevOps | Supply HTTPS endpoints/CA trust and a restricted self-hosted runner labelled `vault-demo`, with Python 3.10+, tested Terraform CLI and Vault/backend reachability. |
| 4. Vault OIDC and access | Vault administrator + implementation lead | Install separate plan/deploy/drift policies and JWT roles in each Vault. Bind exact repository IDs, workflow, main ref and environment subjects; adapt Git settings/expectations to those bindings. No stored Vault credentials or application values in GitHub. |
| 5. First inventory report | Security + implementation lead | Set reviewed release references; run the report; resolve permission gaps and approve intentional differences. Agree report recipients/access, schedule and rotation metadata key/date format/age threshold. `password_cycle_date` and 90 days are examples. |
| 6. Promotion state and imports | DevOps + implementation lead | Choose a protected remote backend with separate state per environment, encryption, locking and recovery. Replace backend placeholders and import existing managed policy/AppRole resources. S3 is an example, not a required backend. |
| 7. Pilot acceptance | Security + application owner | Check guided entry, application access and actual per-environment plans. Promote DEV → UAT → PROD with evidence and approval at each stage. Confirm recovery before production adoption. |

**Current example setup:** ten GitHub environments exist, with main-only deployment restrictions and UAT/PROD reviewer gates preventing self-review. The example's `main` branch is not protected, and no permanent deployment runner is registered. `VAULT_AUTOMATION_ENABLED=false` keeps customer workflows disabled; enable only after the relevant prerequisites are complete. [Detailed setup runbook](RUNBOOK.md).

## Security's daily workflow

| Activity | Security does | Automation does |
| --- | --- | --- |
| New secret | Approve path/keys in Git, then run `./scripts/create-secret.sh --env dev --approve-environment dev` after named Vault authentication. Repeat with each environment's own values. | Guided writer checks the approved schema, creates once and verifies keys without fetching values. |
| Read/edit values | Use Vault UI; update rotation metadata after actual credential rotation. | Value-only edits require no Git change; field/path changes require Git review. |
| Promote configuration | Actions → **Vault promotion** → choose environment; review plan and approve apply. | OIDC authentication, structure check, Terraform plan/apply using that environment's state. |
| Review drift/rotation | Actions → **Daily Vault inventory and rotation** → summary/artifact. | Scheduled at 11:00 UTC or on demand; compares inventories and reports rotation ages. |
| Resolve findings | Promote, adopt an intended change into Git, record an approved exception or correct an error. | No automatic deletion, unused-secret claim or value comparison. |

## Git promotion and file layout

Use protected `main`, short-lived change branches and reviewed PRs. Environment folders contain release references and non-secret overrides, not copied policies.

| Step | Git action | Deployment |
| --- | --- | --- |
| Define | Change branch → reviewed PR → main | Select an immutable configuration commit SHA |
| DEV | PR sets DEV `release.yaml` to that SHA | Plan/apply DEV; record application validation |
| UAT | PR advances UAT to the same SHA | Review DEV evidence; create/apply a UAT plan |
| PROD | PR advances PROD to the same SHA | Review UAT evidence; approve/apply a PROD plan |

Promotion is manually dispatched. Reviewers must check predecessor deployment evidence; automatic enforcement of DEV/UAT success and merge-triggered dispatch are future enhancements. Each environment keeps its own values and state; a DEV plan is never reused in UAT/PROD.

```text
13-Vault-Configuration-Promotion/
├── configuration/
│   ├── application.json          # Expected path and keys
│   ├── policy.hcl.tftpl
│   └── configuration/            # Terraform policy/AppRole pilot
├── environments/{dev,uat,prod}/
│   ├── release.yaml              # Reviewed configuration commit SHA
│   ├── settings.json             # Non-secret target settings/expectations
│   └── *.backend.hcl             # Protected remote state locations
├── scripts/                      # Guided writer, inventory/rotation, pipeline helper
├── bootstrap/                    # Example Vault policies/OIDC role
├── tests/                        # Unit and disposable Vault tests
└── workflow-examples/            # Copies; active workflows at root .github/workflows
```

## Remaining implementation-lead follow-ups

| Follow-up | Status / dependency |
| --- | --- |
| Adapt and validate the customer pilot | Joint setup above; requires customer endpoints, access, application choice and state decisions. |
| Developer keys-only UI | API/CLI proven; validate the customer version/UI and select a supported access route. |
| Unused-path analysis | Requires audit access-history coverage/retention and application-owner confirmation. No standard KV last-access field or automatic deletion is assumed. |
| Separate credential regeneration | Obtain and review the existing operational script before changing this workflow. Current example generates no application tokens or SecretIDs. |

These follow-ups remain open and are not prerequisites for sharing the completed implementation and synthetic test results.

Further reading: [meeting decisions and delivery tracker](MEETING-OUTCOMES.md), [OIDC pilot](OIDC-PILOT.md), [inventory/rotation details](INVENTORY.md). The earlier [advanced Terraform secret-write alternative](ADVANCED-SECRET-WRITES.md) is retained separately; it is not part of the recommended daily workflow and has only syntax/provider validation.
