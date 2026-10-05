# Validation: October 5, 2026

| Check | Result |
| --- | --- |
| Python unit/integration suite | 21 tests passed locally; isolated Vault dev fixtures with restricted identities and synthetic values. |
| Vault / Terraform versions | Vault 2.1.0; Terraform CLI 1.16.1; Vault provider 5.8.0. |
| Keys-only access | Restricted identity reads `subkeys` via API and Vault CLI; data read returns 403. UI rendering was not tested. |
| Drift / rotation | All ACL/password policies; multiple/empty/nested KV v2 mounts; LDAP config/group/user mappings; Kubernetes/token/AppRole roles; userpass; transit/PKI; cross-environment changes in every inventory category; deleted paths and denied/hidden listings passed. Database/Sentinel adapters tested with API fixtures. |
| Dedicated rotation report | `rotation-report.py` extracts age/status across all scanned mounts, flags missing environments and excludes arbitrary metadata. Integrated date cases and report extraction passed. |
| Reports | No synthetic secret values, root/report tokens or arbitrary custom metadata in output. Incomplete evidence cannot report parity; CLI exits distinguish findings and missing reports. |
| Initial writer | Real API create-only write verified; existing path refuses a second write; creator cannot read values. Interactive hidden prompting remains a Security pilot check. |
| Terraform | Both roots pass `fmt -check`, `init -backend=false -lockfile=readonly` and `validate`. Temporary local-state fixture imports existing policy/AppRole, plans/applies and produces a subsequent plan with no changes. Synthetic application values/tokens absent from state. Optional advanced secret-write root received syntax/provider validation only. |
| Workflows | All four root workflows pass actionlint 1.7.7. Reference copies match root promotion/drift workflows. YAML, JSON, Python and shell syntax checks pass. |
| Public content | No customer-specific names or em dashes in Session 13 / workflows. |
| Actions interface | Security-facing Terraform shell wrapper removed; promotion invokes internal `pipeline.py`. Daily report saves both inventory comparison and rotation artifacts. |
| Cleanup | Test Vault processes terminated; temporary test directories/logs removed. |

## GitHub execution evidence

| Run | Result / evidence |
| --- | --- |
| [Validation workflow](https://github.com/tekanaid-user/vault-in-vmware/actions/runs/37376406133) | Passed on an isolated ephemeral runner: 21 tests, real Terraform fixture apply/idempotence/state checks, both root validations and CLI/shell checks. Revision `75018c6`. |
| [Real OIDC pilot](https://github.com/tekanaid-user/vault-in-vmware/actions/runs/37376409400) | Passed at `75018c6`: three loopback TLS Vaults, real GitHub-issued JWTs, exact immutable subject bindings, rejected untrusted repository bindings, denied data reads, scoped Terraform plan/apply, complete supported-inventory parity, and detected UAT field/rotation drift. Values-free artifact downloaded and checked. |
| Runner cleanup | API reported zero registered runners after completion; no pilot containers remained. TLS keys, synthetic values, plans, local state and server logs were disposable. |
| Repository setup | Ten GitHub environments restricted to main; UAT/PROD reviewer gates with self-review prevented; repository secrets count zero. Live endpoint switch remains false. |

The initial hosted jobs were queued and cancelled; successful runs used isolated disposable Docker runners registered to GitHub. These are real GitHub workflow/OIDC results against synthetic Vaults, not customer DEV/UAT/PROD evidence. Remote state storage, on-prem connectivity and customer deployments remain untested. Live workflows require actual endpoints/state/runner setup and `VAULT_AUTOMATION_ENABLED=true`; see [runbook](RUNBOOK.md).

The expanded inventory, full KV structure parity and legacy-report guard passed locally and in GitHub Actions. Unsupported plugin details and excluded server/credential settings are documented in [INVENTORY.md](INVENTORY.md).
