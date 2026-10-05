# Validation: October 5, 2026

| Check | Result |
| --- | --- |
| Python unit/integration suite | 11 tests passed; three isolated local Vault dev servers with synthetic values. |
| Vault / Terraform versions | Vault 2.1.0; Terraform CLI 1.16.1; Vault provider 5.8.0. |
| Keys-only access | Restricted identity reads `subkeys` via API and Vault CLI; data read returns 403. UI rendering was not tested. |
| Drift / rotation | Field/path, nested structure, policy/AppRole/KV configuration, deleted path, rotation-date and permission-failure cases passed. |
| Reports | No synthetic secret values, root/report tokens or arbitrary custom metadata in output. Incomplete evidence cannot report parity; CLI exits distinguish findings and missing reports. |
| Initial writer | Real API create-only write verified; existing path refuses a second write; creator cannot read values. Interactive hidden prompting remains a Security pilot check. |
| Terraform | Both roots pass `fmt -check`, `init -backend=false -lockfile=readonly` and `validate`. Temporary local-state fixture imports existing policy/AppRole, plans/applies and produces a subsequent plan with no changes. Synthetic application values/tokens absent from state. Optional advanced secret-write root received syntax/provider validation only. |
| Workflows | All four root workflows pass actionlint 1.7.7. Reference copies match root promotion/drift workflows. YAML, JSON, Python and shell syntax checks pass. |
| Public content | No customer-specific names or em dashes in Session 13 / workflows. |
| Cleanup | Test Vault processes terminated; temporary test directories/logs removed. |

## GitHub execution evidence

| Run | Result / evidence |
| --- | --- |
| [Validation workflow](https://github.com/tekanaid-user/vault-in-vmware/actions/runs/37371190326) | Passed on an isolated ephemeral runner: 11 tests, real Terraform fixture apply/idempotence/state checks, both root validations and CLI/shell checks. Revision `c203bc6`. |
| [Real OIDC pilot](https://github.com/tekanaid-user/vault-in-vmware/actions/runs/37371373304) | Passed at `c4a82da`: three loopback TLS Vaults, real GitHub-issued JWTs, exact immutable subject bindings, rejected untrusted repository bindings, denied data reads, scoped Terraform plan/apply, and detected UAT field/rotation drift. Values-free artifact downloaded and checked. |
| Runner cleanup | API reported zero registered runners after completion; no pilot containers remained. TLS keys, synthetic values, plans, local state and server logs were disposable. |
| Repository setup | Ten GitHub environments restricted to main; UAT/PROD reviewer gates with self-review prevented; repository secrets count zero. Live endpoint switch remains false. |

The initial hosted jobs were queued and cancelled; successful runs used isolated disposable Docker runners registered to GitHub. These are real GitHub workflow/OIDC results against synthetic Vaults, not customer DEV/UAT/PROD evidence. Remote state storage, on-prem connectivity and customer deployments remain untested. Live workflows require actual endpoints/state/runner setup and `VAULT_AUTOMATION_ENABLED=true`; see [runbook](RUNBOOK.md).
