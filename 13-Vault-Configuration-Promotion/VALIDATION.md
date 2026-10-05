# Validation: October 5, 2026

| Check | Result |
| --- | --- |
| Python unit/integration suite | 26 tests passed locally; isolated Vault dev fixtures with restricted identities and synthetic values. |
| Vault / Terraform versions | Vault 2.1.0; Terraform CLI 1.16.1; Vault provider 5.8.0. |
| Keys-only access | Restricted identity reads `subkeys` via API and Vault CLI; data read returns 403. UI rendering was not tested. |
| Drift / rotation | All ACL/password policies; multiple/empty/nested KV v2 mounts; LDAP config/group/user mappings; Kubernetes/token/AppRole roles; userpass; transit/PKI; cross-environment changes in every inventory category; deleted paths and denied/hidden listings passed. Database adapters tested with API fixtures; historical Sentinel fixture is not customer Community scope. |
| Dedicated rotation report | `rotation-report.py` extracts age/status across all scanned mounts, flags missing environments and excludes arbitrary metadata. Integrated date cases and report extraction passed. |
| Reports | No synthetic secret values, root/report tokens or arbitrary custom metadata in output. Incomplete evidence cannot report parity; CLI exits distinguish findings and missing reports. |
| Historical initial-writer utility | Real API create-only write verified; existing path refuses a second write; creator cannot read values. Retained under tests/fixtures only; not Security's daily workflow. |
| Terraform | Both roots pass `fmt -check`, `init -backend=false -lockfile=readonly` and `validate`. Temporary local-state fixture imports existing policy/AppRole, plans/applies and produces a subsequent plan with no changes. Synthetic application values/tokens absent from state. Superseded optional staged secret-write example removed. |
| Workflows | All active root workflows pass actionlint 1.7.7; duplicate reference copies removed. YAML, JSON, Python and shell syntax checks pass. |
| Public content | No customer-specific names or em dashes in Session 13 / workflows. |
| Actions interface | Security-facing Terraform shell wrapper removed; admin request/deploy/credential Actions invoke internal Python helpers. Daily report saves both inventory comparison and rotation artifacts. |
| Cleanup | Test Vault processes terminated; temporary test directories/logs removed. |

## Admin script conversion: current test evidence

Target is Vault Community Edition with no namespaces; nonempty namespace configuration is rejected.

| Check | Verified locally against disposable Vault |
| --- | --- |
| Parameter validation | Multiple names accepted; reserved/traversal/shell names, unknown settings, invalid CIDRs and boolean TTLs rejected. Configure → reviewed-release generation and retention of managed apps/restart tested in an isolated Git fixture. |
| Terraform helper | Actual `admin-pipeline.plan()` imports existing KV/auth/policy/AppRole resources using a scoped plan identity. Scoped deploy applies the saved plan restored into a different directory. Multiple apps and restart setup created; second plan is unchanged. |
| Safety | Existing synthetic UI-equivalent values preserved, tokens/values absent from state and summaries; deletion plans rejected; provisioning generates no restart SecretIDs. Restricted plan/deploy identities cannot read application values. |
| Integrity | Saved-plan/manifest tampering and wrong target rejected by the actual artifact verifier. |
| Deliberate issuance | Scoped identity delivers restart credentials to Vault KV, cannot read application/delivery values, and stale delivery version prevents another issuance. Failed delivery cleanup/revocation also verified locally. |

**Verification boundary:** local tests exercise the actual helpers and a restored saved plan. They do not establish real GitHub cross-job upload/download, reviewer approval, customer remote state, customer UI behavior or customer deployments. The earlier real OIDC pilot remains evidence for authentication/reporting and the original one-app Terraform fixture, not the new admin deploy workflow end to end.

## GitHub execution evidence

| Current conversion evidence | Result |
| --- | --- |
| [25-test validation](https://github.com/tekanaid-user/vault-in-vmware/actions/runs/37384624959) | Passed at `284d79a`, including actual admin helper, scoped identities, portable saved plan, integrity and Community namespace rejection. |
| [Security parameter form](https://github.com/tekanaid-user/vault-in-vmware/actions/runs/37384643968) | Passed at `284d79a`: dispatched configure/both for one synthetic app and created a catalog PR using the job's GitHub token. Test PR was closed without merge; no Vault writes. |



| Run | Result / evidence |
| --- | --- |
| [Validation workflow](https://github.com/tekanaid-user/vault-in-vmware/actions/runs/37376406133) | Passed on an isolated ephemeral runner: 21 tests, real Terraform fixture apply/idempotence/state checks, both root validations and CLI/shell checks. Revision `75018c6`. |
| [Real OIDC pilot](https://github.com/tekanaid-user/vault-in-vmware/actions/runs/37376409400) | Passed at `75018c6`: three loopback TLS Vaults, real GitHub-issued JWTs, exact immutable subject bindings, rejected untrusted repository bindings, denied data reads, scoped Terraform plan/apply, complete supported-inventory parity, and detected UAT field/rotation drift. Values-free artifact downloaded and checked. |
| Runner cleanup | API reported zero registered runners after completion; no pilot containers remained. TLS keys, synthetic values, plans, local state and server logs were disposable. |
| Repository setup | Ten GitHub environments restricted to main; UAT/PROD reviewer gates with self-review prevented; repository secrets count zero. Live endpoint switch remains false. |

The initial hosted jobs were queued and cancelled; successful runs used isolated disposable Docker runners registered to GitHub. These are real GitHub workflow/OIDC results against synthetic Vaults, not customer DEV/UAT/PROD evidence. Remote state storage, on-prem connectivity and customer deployments remain untested. Live workflows require actual endpoints/state/runner setup and `VAULT_AUTOMATION_ENABLED=true`; see [runbook](RUNBOOK.md).

The expanded inventory, full KV structure parity and legacy-report guard passed locally and in GitHub Actions. Unsupported plugin details and excluded server/credential settings are documented in [INVENTORY.md](INVENTORY.md).
