# October 5, 2026: decisions and delivery tracker

The team agreed to Git as the source of truth for configuration and secret structure, with two workstreams. The target is Vault Community Edition, with no namespaces. Security retains UI access and each environment keeps its own values. Start with read-only reporting, then pilot promotion for one application. This public summary contains no organization or attendee details beyond the implementation owner.

| Workstream | Agreed direction | Implementation in this folder |
| --- | --- | --- |
| 1: Entry and promotion | Security uses parameter-driven GitHub Actions; values entered/read/edited in Vault UI; Terraform Community CLI operated through GitHub Actions; reviewed Git releases DEV → UAT → PROD | Parameter form creates reviewed catalog/release PRs; admin deployment uses Terraform for multiple apps and restart configuration. Requires live setup and pilot acceptance. |
| 2: Drift and rotation | Daily read-only comparison against Git and across environments; Security reviews results | Metadata/subkeys collector, all ACL/password policies, auth/engine inventory, supported configuration adapters, rotation-age findings and scheduled Actions workflow. No value reads or corrections. |

## Current workflow learned

| Area | Meeting finding |
| --- | --- |
| Scripts | One Linux host runs modified shell scripts against three environments; supports multiple application names, optional seeding and credential generation. |
| Promotion | DEV ticket first; UAT/PROD tickets later. Policies generally match if application names match. No complete Git baseline today. |
| UI | Actual values, LDAP/group configuration and password-cycle metadata are managed through the UI. Retain this flexibility. |
| Renames | Copy/recreate/reseed can leave old paths/policies behind. Review with application owners before removing anything. |
| Differences | LDAP/developer permissions and values differ. CIDR restrictions are not enabled; future CIDRs would differ per environment. |
| Rotation | Custom metadata records password-cycle dates, with incomplete coverage. Last updated is not proof of rotation or last access. |

## Action tracker and repo mapping

| Action | Owner | Status / next checkpoint | Repo location |
| --- | --- | --- | --- |
| Full drift inventory and rotation report | Sam | Built/tested; 26-test Actions validation and earlier real OIDC pilot passed. Review first environment report. | [Inventory](scripts/inventory.py); [Drift](scripts/drift.py); [Rotation](scripts/rotation-report.py) |
| Security onboarding parameters | Sam + DevOps | Built; actual GitHub form created a synthetic catalog PR. Configure/promote form uses non-secret names/settings and reviewed Git changes. | [Request Action](../.github/workflows/vault-admin-request.yml); [Form helper](scripts/admin-request.py) |
| Verify complete Security pipeline | Sam + DevOps | Helper tests passed: scoped imports/plan, restored saved-plan apply, integrity and preserved values. Full GitHub approval/artifact deployment and environment remote backend remain open. | [Deploy Action](../.github/workflows/vault-admin-deploy.yml); [Helper](scripts/admin-pipeline.py); [Tests](tests/test_admin.py); [Evidence](VALIDATION.md) |
| Configure environment access and report review | DevOps + Security, with Sam | Vault Community Edition, no namespaces. Confirm endpoints/CA, mount/policy scope, runner, OIDC, protected main/reviewers, report access, cadence and exceptions. | [Setup runbook](RUNBOOK.md); [Environment settings](environments/); [Policy examples](bootstrap/) |
| Select/import promotion pilot | Security + DevOps, with Sam | Choose one application; approve catalog settings and state. Existing supported resources auto-import before plan; review adoption changes. | [Catalog](configuration/admin-catalog.json); [Terraform](configuration/admin-setup/main.tf); [Environment releases/state](environments/) |
| Validate environment DEV → UAT → PROD | Security + DevOps/application owner, with Sam | Pending environment setup: same approved SHA, separate plans/state, reviewer approval, application access, Vault UI entry and recovery. | [Deploy Action](../.github/workflows/vault-admin-deploy.yml); [Acceptance checklist](RUNBOOK.md) |
| Developer keys-only access | Sam | API/CLI proven with value reads denied. Vault Community UI behavior still open. | [Developer policy](bootstrap/developer-keys-policy.hcl); [Coverage](INVENTORY.md) |
| Agree rotation metadata and threshold | Security + Sam | Report built/tested. Confirm field, ISO date format and maximum age; 90 days is an example. | [Rotation report](scripts/rotation-report.py); [Settings](environments/); [Report Action](../.github/workflows/vault-drift.yml) |
| Investigate unused-path evidence | Sam + Security/application owners | Still open: audit history/retention and owner confirmation. No last-access report or deletion automation implemented. | [Evidence checklist](RUNBOOK.md#unused-path-evidence) |
| Separate credential regeneration | Sam + Security | Built/tested as a deliberate protected Action. Credentials go directly to restricted Vault KV. Confirm delivery readers, TTL/use limits and revocation process. | [Issuance Action](../.github/workflows/vault-restart-credentials.yml); [Delivery helper](scripts/restart-credentials.py); [Issuer policy](bootstrap/restart-credential-policy.hcl) |
| Catalog-wide Git compliance | Sam | Remaining extension: full cross-environment inventory is built, but Git baseline checks currently cover the selected original app and configured expected fields, not every new catalog app. | [Coverage/boundary](README.md#what-is-scanned); [Collector](scripts/drift.py) |
| Finish Splunk alerts and retention | Security + log analysts/Splunk team | Root-token use, root-policy changes and human reads; confirm invalid-token follow-up, audit/syslog retention and cover during absence. | [Meeting follow-ups](MEETING-OUTCOMES.md#team-dependencies-and-next-session) |
| Operational-log ticket / Help Desk note | Internal request owner, TBC | Confirm submission, scope, retention questions and tracking tickets. No ticket automation committed to Sam. | [Meeting follow-ups](MEETING-OUTCOMES.md#team-dependencies-and-next-session) |
| Datadog test and rollout | Vault operations + monitoring team | Telemetry added on separate test server; configure Agent and verify metrics before fleet rollout. | [Meeting follow-ups](MEETING-OUTCOMES.md#team-dependencies-and-next-session) |
| Next-meeting invite | Meeting organizer, TBC | Confirm October 13, 2:30, time zone and attendees. | [Meeting follow-ups](MEETING-OUTCOMES.md#team-dependencies-and-next-session) |

## Team dependencies and next session

| Follow-up | Owner / status reported |
| --- | --- |
| Splunk alerts | Security with log analysts: root-token use, root-policy changes, human secret reads in UAT/PROD. Earlier invalid-token item not confirmed closed. |
| Help-desk / tracking note | Confirm the promised note and related tracking tickets were submitted; completion was not established in the meeting. |
| Operational logs and retention | Submit log ticket; confirm audit/syslog retention, filtering and rotated-file coverage. Ticket completion was not confirmed. |
| Datadog | Vault telemetry added successfully on a separate test server. Configure Agent side and verify metrics before fleet rollout. |
| Next session | Tuesday October 13, 2:30 proposed; confirm invite/time zone/attendance. Recap outstanding work before new features; LDAP secrets engine is a candidate topic. |

Operator handoff: [built/tested summary, environment prerequisites and remaining implementation follow-ups](README.md).

Source: the two supplied October 5 meeting transcript segments. Detailed internal meeting notes stay outside this public repository.

Direct mapping of every implementation commitment to code, Actions and remaining checkpoints: [README delivery table](README.md#sams-commitments-direct-repo-mapping).
