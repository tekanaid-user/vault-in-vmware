# October 5, 2026: decisions and delivery tracker

The team agreed to Git as the source of truth for configuration and secret structure, with two workstreams. The target is Vault Community Edition, with no namespaces. Security retains UI access and each environment keeps its own values. Start with read-only reporting, then pilot promotion for one application. This public summary contains no customer or attendee details beyond the implementation owner.

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

## Implementation delivery items

| Item | Status here | Remaining evidence / dependency |
| --- | --- | --- |
| Share full drift inventory/report | Implemented: all auth/engine mounts, ACL/password policies, accessible KV v2 paths/keys and supported configs | Disposable TLS/OIDC pilot passed in GitHub Actions with an isolated ephemeral runner; configure live scopes/releases and review a real-environment report with Security. |
| Keys-only developer access | API and `vault read secret/subkeys/...` tested with data-read denied | Validate installed Vault version and UI behavior. API/CLI support does not prove UI support. |
| Rotation-age report | Implemented/tested: integrated scan plus dedicated `rotation-report.py`; daily Actions artifact | Confirm exact metadata key, ISO date format and agreed age threshold; 90 days is a placeholder. |
| Security pipeline interface | Admin request form creates catalog/release PRs; separate admin deploy Action; no Security-run scripts | Validate customer use of the implemented parameter form and Vault UI; see README for direct Actions links. |
| GitHub Actions promotion interface / pilot | Workflow template implemented; components tested; full approval/artifact flow unverified | Example environment/review gates configured; main branch protection and customer reviewer assignments remain; disposable pilot passed. Choose customer application, import scope, remote backend and a reachable self-hosted runner. Confirm live TTL/use settings before adopting example defaults. |
| Complete Security workflow verification | Helper tests implemented | Actual admin plan/import and portable saved-plan apply, input validation, scoped identities and integrity checks tested locally. Full GitHub cross-job/reviewer flow and customer backend remain acceptance items. |
| Unused-path evidence | No automatic deletion | Investigate available audit access history and retention; verify candidates with application owners. KV metadata has no standard last-access field. |
| Separate credential regeneration | Separate issuance Action implemented/tested | Current script reviewed. Configuration creates no credentials; deliberate issuance delivers restart credentials directly to restricted Vault KV. Customer approves readers, TTLs and revocation. |

## Team dependencies and next session

| Follow-up | Owner / status reported |
| --- | --- |
| Splunk alerts | Security with log analysts: root-token use, root-policy changes, human secret reads in UAT/PROD. Earlier invalid-token item not confirmed closed. |
| Help-desk / tracking note | Confirm the promised note and related tracking tickets were submitted; completion was not established in the meeting. |
| Operational logs and retention | Submit log ticket; confirm audit/syslog retention, filtering and rotated-file coverage. Ticket completion was not confirmed. |
| Datadog | Vault telemetry added successfully on a separate test server. Configure Agent side and verify metrics before nine-server rollout. |
| Next session | Tuesday October 13, 2:30 proposed; confirm invite/time zone/attendance. Recap outstanding work before new features; LDAP secrets engine is a candidate topic. |

Customer handoff: [built/tested summary, customer prerequisites and remaining implementation follow-ups](README.md).

Source: the two supplied October 5 meeting transcript segments. Detailed internal meeting notes stay outside this public repository.

Direct mapping of every implementation commitment to code, Actions and remaining checkpoints: [README delivery table](README.md#sams-commitments-direct-repo-mapping).
