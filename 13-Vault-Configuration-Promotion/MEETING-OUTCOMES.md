# October 5, 2026: decisions and delivery tracker

The team agreed to Git as the source of truth for configuration and secret structure, with two workstreams. Security retains UI access and each environment keeps its own values. Start with read-only reporting, then pilot promotion for one application. This public summary contains no customer or attendee details beyond the implementation owner.

| Workstream | Agreed direction | Implementation in this folder |
| --- | --- | --- |
| 1: Entry and promotion | Guided initial entry; UI reads/value edits; Terraform Community CLI operated through GitHub Actions; reviewed Git releases DEV → UAT → PROD | Create-only hidden-prompt writer, internal plan/apply helper, manual promotion Actions workflow. Requires live setup/imports and pilot validation. |
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

## Sam's delivery items

| Item | Status here | Remaining evidence / dependency |
| --- | --- | --- |
| Share full drift inventory/report | Implemented: all auth/engine mounts, ACL/password policies, accessible KV v2 paths/keys and supported configs | Disposable TLS/OIDC pilot passed in GitHub Actions with an isolated ephemeral runner; configure live scopes/releases and review a real-environment report with Security. |
| Keys-only developer access | API and `vault read secret/subkeys/...` tested with data-read denied | Validate installed Vault version and UI behavior. API/CLI support does not prove UI support. |
| Rotation-age report | Implemented/tested: integrated scan plus dedicated `rotation-report.py`; daily Actions artifact | Confirm exact metadata key, ISO date format and agreed age threshold; 90 days is a placeholder. |
| Guided initial writer | Implemented: Git fields, hidden prompts, direct Vault write, CAS=0 | Pilot Security's named identity and terminal workflow. No overwrite, Terraform state or GitHub value entry. |
| GitHub Actions promotion interface / pilot | Implemented; Security-facing Terraform shell wrapper removed | GitHub environments/review gates configured; disposable pilot added. Choose customer application, import scope, remote backend and a reachable self-hosted runner. Confirm live TTL/use settings before adopting example defaults. |
| Unused-path evidence | No automatic deletion | Investigate available audit access history and retention; verify candidates with application owners. KV metadata has no standard last-access field. |
| Separate credential regeneration | Design follow-up | Obtain/review the current operational script. This example creates no SecretIDs or application tokens. |

## Team dependencies and next session

| Follow-up | Owner / status reported |
| --- | --- |
| Splunk alerts | Security with log analysts: root-token use, root-policy changes, human secret reads in UAT/PROD. Earlier invalid-token item not confirmed closed. |
| Operational logs and retention | Submit log ticket; confirm audit/syslog retention, filtering and rotated-file coverage. Ticket completion was not confirmed. |
| Datadog | Vault telemetry added successfully on a separate test server. Configure Agent side and verify metrics before nine-server rollout. |
| Next session | Tuesday October 13, 2:30 proposed; confirm invite/time zone/attendance. Recap outstanding work before new features; LDAP secrets engine is a candidate topic. |

Source: the two supplied October 5 meeting transcript segments. Detailed internal meeting notes stay outside this public repository.
