# Read the report collected from the local Vault lab

These reports were **collected from three running TLS Vault servers on the development machine**, using the actual `drift.py` CLI and read-only tokens. They are not manually assembled inventories. The servers contain deliberately seeded non-production test data; they are not recipient environments.

Start with [the readable report](report.md). Source collector output: [DEV](dev.json), [UAT](uat.json), [PROD](prod.json). Derived outputs: [comparison.json](comparison.json) and [rotation-report.json](rotation-report.json). [evidence.json](evidence.json) records collection time, Vault version, source boundary and checks.

## Observed differences

The complete supported scan found **22 differences** across all five categories. Rotation reported **11 current, 1 overdue, 1 missing, 1 invalid and 1 future date**. Counts describe this captured lab run; regenerating after edits or as dates age can change them.

| Actual local finding | Difference detected | Review interpretation |
| --- | --- | --- |
| ACL policies | UAT `acl/application-reader` differs; `acl/dev-only` exists only in DEV. | Review policy intent; raw text is excluded from reports. |
| Password policy | `password/application` has a different length in PROD. | Reports configuration without generating passwords. |
| Auth method | `local-users/` exists only in DEV. | Extra mount, tuning and user settings are visible. |
| Secrets engine | `prototype/` exists only in DEV. | Mount differences are distinct from secret-path differences. |
| AppRole | UAT `example-app` token TTL differs. | Field differences without fetching RoleIDs/SecretIDs. |
| LDAP mapping | PROD developer-group policies differ. | API configuration/mapping inventory, not directory login validation. |
| KV config/tuning | UAT `max_versions` and PROD lease tuning differ. | Review intended overrides. |
| PKI/transit | PROD disables subdomains and has an extra transit key. | No key export or certificate issuance by reporting. |
| Nested fields | PROD adds `connection/region` at `apps/service/config`. | Field names, not values. |
| Missing field | UAT lacks `password` at `secret/example-app/config`. | Check expected structure/change request. |
| Extra old path | DEV has `secret/example-app-old/config` without a date. | Investigate owner/audit history before cleanup. |
| Deleted path | `secret/retired/config` is soft-deleted in PROD. | Deletion is not silently treated as parity. |
| Rotation | UAT 120 days old; DEV missing/invalid dates; PROD future date. | Metadata quality and rotation timing are separate findings. |
| JWT subject | `bound_claims/sub` differs per environment. | Intentional scoping remains visible because this lab preapproves no exceptions. |

`complete: true` plus `has_findings: true` gives the weekly report's **exit 2** classification. An actual denied-token scan and missing-environment comparison were also verified: unknown/incomplete/null parity, never a clean report. Real value GETs returned **403** on default, additional and nested KV mounts in every environment.

`same_selected_release` and `all_policies_match_selected_git` are `null` in inventory-only mode. Cross-environment comparison is real; this run does not assert catalog-wide Git compliance. Review unsupported/excluded details even with complete supported inventory.

## Real GitHub OIDC evidence

A separate [successful GitHub Actions run](https://github.com/tekanaid-user/vault-in-vmware/actions/runs/38474723943) on a local ephemeral container runner exchanged real GitHub JWTs against three disposable TLS Vaults. It verified rejected repository bindings, readable subkeys/denied values, introduced UAT drift and scoped Terraform plan/apply followed by an unchanged plan.

[oidc-evidence.json](oidc-evidence.json) records the run/artifact checksum; [oidc-pilot-report.json](oidc-pilot-report.json) is the actual downloaded artifact. This proves federation against disposable fixtures. The longer-running localhost lab report uses fresh scoped local tokens; it is not the weekly workflow connecting to those endpoints.

## Reproduce and review

Follow [LOCAL-LAB.md](../LOCAL-LAB.md) to start the servers, collect twice and run tests. The same collectors/comparison/rendering are used by Actions. Never seed this lab into an existing production Vault.

For the weekly workflow, read the Summary and download `vault-drift-comparison` for Markdown/comparison/rotation files; per-environment artifacts contain inventories. Local collection writes equivalent outputs here. Actions retention is seven days. Reporting makes no corrections/deletions and does not implement last-access analysis.
