# Local validation: October 5, 2026

| Check | Result |
| --- | --- |
| Python unit/integration suite | 11 tests passed; three isolated local Vault dev servers with synthetic values. |
| Vault / Terraform versions | Vault 2.1.0; Terraform CLI 1.16.1; Vault provider 5.8.0. |
| Keys-only access | Restricted identity reads `subkeys` via API and Vault CLI; data read returns 403. UI rendering was not tested. |
| Drift / rotation | Field/path, nested structure, policy/AppRole/KV configuration, deleted path, rotation-date and permission-failure cases passed. |
| Reports | No synthetic secret values, root/report tokens or arbitrary custom metadata in output. Incomplete evidence cannot report parity; CLI exits distinguish findings and missing reports. |
| Initial writer | Real API create-only write verified; existing path refuses a second write; creator cannot read values. Interactive hidden prompting remains a Security pilot check. |
| Terraform | Both roots pass `fmt -check`, `init -backend=false -lockfile=readonly` and `validate`. Temporary local-state fixture imports existing policy/AppRole, plans/applies and produces a subsequent plan with no changes. Synthetic application values/tokens absent from state. Optional advanced secret-write root received syntax/provider validation only. |
| Workflows | All three root workflows pass actionlint 1.7.7. Reference copies match root promotion/drift workflows. YAML, JSON, Python and shell syntax checks pass. |
| Public content | No customer-specific names or em dashes in Session 13 / workflows. |
| Cleanup | Test Vault processes terminated; temporary test directories/logs removed. |

These are local synthetic results. GitHub-hosted workflow execution, OIDC federation, remote state storage, on-prem connectivity and customer DEV/UAT/PROD deployments were not tested. Live workflows require setup and `VAULT_AUTOMATION_ENABLED=true`; see [runbook](RUNBOOK.md).
