# Vault configuration, drift and rotation

Security operates **GitHub Actions**, supplying non-secret parameters. Actions runs Terraform Community CLI; Security does not run scripts or learn Terraform. **Vault Community Edition, with no namespaces.** Git holds configuration and expected structure. Vault holds environment-specific values, with UI access retained.

**Status:** [26-test Actions validation](https://github.com/tekanaid-user/vault-in-vmware/actions/runs/37385293464) and [actual parameter-form PR creation](https://github.com/tekanaid-user/vault-in-vmware/actions/runs/37384643968) passed. Customer DEV/UAT/PROD endpoints, state, runners and acceptance remain pending. Live deployment/reporting is disabled until setup is complete. [Test evidence and limits](VALIDATION.md).

## Actions and daily workflow

| Step | Security does | Pipeline result |
| --- | --- | --- |
| 1. Define/change application | [Vault admin change request](https://github.com/tekanaid-user/vault-in-vmware/actions/workflows/vault-admin-request.yml): select `configure`; enter application names, key names, mode and ticket. Optional JSON sets AppRole TTLs/use limits/CIDRs. | Creates a PR for `configuration/admin-catalog.json`. No Vault writes. Review and merge. |
| 2. Select release | Same Action: select `promote`, DEV, applications and the full reviewed configuration commit SHA. | Creates a PR for DEV `admin-release.json`. Review and merge. Existing managed applications are retained. |
| 3. Deploy configuration | [Vault admin deploy](https://github.com/tekanaid-user/vault-in-vmware/actions/workflows/vault-admin-deploy.yml): select DEV. Review plan; approve apply when required. | Scoped OIDC, import existing configuration, Terraform saved plan, separate approved apply. Deletes/replacements are blocked. |
| 4. Supply/read/edit values | Vault UI, under `secret/<application>/<entry>`, for example `secret/webapp/config`. Enter each environment's own JSON values. | No application values in GitHub inputs/secrets, Git or Terraform state. No sample secrets are seeded. |
| 5. Promote | Repeat steps 2 and 3 for UAT, then PROD, with the **same configuration SHA**. Check prior environment evidence. | Separate state and plans per environment; values are never copied. Prior-environment success is checked by reviewers, not automatically enforced. Reviewed `admin_application_overrides` in environment settings allow different CIDRs/role settings while sharing a release SHA. |
| 6. Review reports | [Daily Vault inventory and rotation](https://github.com/tekanaid-user/vault-in-vmware/actions/workflows/vault-drift.yml), daily at 11:00 UTC or on demand. | Read-only DEV/UAT/PROD comparison and rotation-age artifacts. No automatic corrections/deletions. |
| Separate deliberate operation | [Vault restart credential issuance](https://github.com/tekanaid-user/vault-in-vmware/actions/workflows/vault-restart-credentials.yml): select environment and current delivery version. | Approved job writes new restart RoleID/SecretID directly into restricted Vault KV. Never prints or stores them in artifacts/state. Retrieve through Vault UI. Old credentials are not automatically revoked. |

### Mapping from the existing admin script

Source: [Session 8/9 admin script](../09-Session8and9-UpdatingScripts/ScriptsPerPersona/vault-admin-setup.sh).

| Original operation | New behavior |
| --- | --- |
| Multiple application names | Space-separated `applications` form input, validated; no silent default applications. |
| Application policies, AppRoles, KV v2 mount, AppRole auth | Terraform `configuration/admin-setup`; existing resources imported before plan. Policy adds metadata listing for application paths. |
| Restart / applications / both | `setup_mode` input; reviewed release retains the previously managed set. Restart policy is limited to selected applications, replacing the original wildcard. |
| Hardcoded TTLs/use counts/CIDRs | Defaults preserve application TTLs/counts: SecretID 24h/150 uses, token 5h/24h maximum/100 uses. CIDRs default empty; original loopback demo CIDRs must be replaced with reviewed customer ranges. Restart retains original unlimited defaults until reviewed. |
| Token/LDAP prompt | GitHub OIDC machine identity; human LDAP access remains. No routine root token. |
| Optional secret seeding | Vault UI, after configuration deployment; no values accepted by Actions. |
| Restart SecretID generated during setup | Separate protected issuance Action with compare-and-set delivery. Provisioning never generates credentials. |
| Printed/saved credentials | Vault delivery path `automation-delivery/restart/credentials`; reader access controlled separately. |

## Sam's commitments: direct repo mapping

Every implementation commitment has a location and an explicit remaining checkpoint. [Detailed customer setup](RUNBOOK.md).

| Commitment | Owner | Repo location | Status / remaining checkpoint |
| --- | --- | --- | --- |
| Full drift inventory and rotation report | Sam | [Inventory](scripts/inventory.py); [Drift](scripts/drift.py); [Rotation](scripts/rotation-report.py) | Built/tested; 26-test Actions validation and earlier real OIDC pilot passed. Review first customer report. |
| Security onboarding parameters | Sam + DevOps | [Request Action](../.github/workflows/vault-admin-request.yml); [Form helper](scripts/admin-request.py) | Built; actual GitHub form created a synthetic catalog PR. Configure/promote form uses non-secret names/settings and reviewed Git changes. |
| Verify complete Security pipeline | Sam + DevOps | [Deploy Action](../.github/workflows/vault-admin-deploy.yml); [Helper](scripts/admin-pipeline.py); [Tests](tests/test_admin.py); [Evidence](VALIDATION.md) | Helper tests passed: scoped imports/plan, restored saved-plan apply, integrity and preserved values. Full GitHub approval/artifact deployment and customer remote backend remain open. |
| Configure customer access and report review | DevOps + Security, with Sam | [Setup runbook](RUNBOOK.md); [Environment settings](environments/); [Policy examples](bootstrap/) | Vault Community Edition, no namespaces. Confirm endpoints/CA, mount/policy scope, runner, OIDC, protected main/reviewers, report access, cadence and exceptions. |
| Select/import promotion pilot | Security + DevOps, with Sam | [Catalog](configuration/admin-catalog.json); [Terraform](configuration/admin-setup/main.tf); [Environment releases/state](environments/) | Choose one application; approve catalog settings and state. Existing supported resources auto-import before plan; review adoption changes. |
| Validate customer DEV → UAT → PROD | Security + DevOps/application owner, with Sam | [Deploy Action](../.github/workflows/vault-admin-deploy.yml); [Acceptance checklist](RUNBOOK.md) | Pending customer setup: same approved SHA, separate plans/state, reviewer approval, application access, Vault UI entry and recovery. |
| Developer keys-only access | Sam | [Developer policy](bootstrap/developer-keys-policy.hcl); [Coverage](INVENTORY.md) | API/CLI proven with value reads denied. Customer Vault Community UI behavior still open. |
| Agree rotation metadata and threshold | Security + Sam | [Rotation report](scripts/rotation-report.py); [Settings](environments/); [Report Action](../.github/workflows/vault-drift.yml) | Report built/tested. Confirm field, ISO date format and maximum age; 90 days is an example. |
| Investigate unused-path evidence | Sam + Security/application owners | [Evidence checklist](RUNBOOK.md#unused-path-evidence) | Still open: audit history/retention and owner confirmation. No last-access report or deletion automation implemented. |
| Separate credential regeneration | Sam + Security | [Issuance Action](../.github/workflows/vault-restart-credentials.yml); [Delivery helper](scripts/restart-credentials.py); [Issuer policy](bootstrap/restart-credential-policy.hcl) | Built/tested as a deliberate protected Action. Credentials go directly to restricted Vault KV. Confirm delivery readers, TTL/use limits and revocation process. |
| Catalog-wide Git compliance | Sam | [Coverage/boundary](README.md#what-is-scanned); [Collector](scripts/drift.py) | Remaining extension: full cross-environment inventory is built, but Git baseline checks currently cover the selected original app and configured expected fields, not every new catalog app. |

## What is scanned

All accessible KV v2 mounts and paths in each Vault Community instance, nested keys via subkeys, ACL/password policies, auth/engine mounts, and supported configuration adapters including LDAP mappings. Unsupported plugin details and failed/denied reads are explicit; incomplete scans cannot report equality. [Exact coverage](INVENTORY.md).

Cross-environment comparison covers the full supported inventory. The current Git-baseline collector covers the original selected application's definition and configured expected fields; it does not yet reconcile every admin catalog entry against Git. Treat catalog-wide Git compliance as a remaining extension. Rotation uses operator-maintained custom metadata, not last-updated or inferred last-access dates.

## Layout and cleanup

```text
.github/workflows/vault-*.yml         # Active Actions, one canonical copy
13-Vault-Configuration-Promotion/
├── configuration/admin-catalog.json # Shared non-secret definitions
├── configuration/admin-setup/       # Current admin Terraform root
├── environments/{dev,uat,prod}/
│   ├── admin-release.json           # Full reviewed SHA and managed apps/mode
│   ├── admin-setup.backend.hcl       # Environment-specific remote state
│   └── settings.json               # Endpoint, OIDC and report settings
├── scripts/                        # Internal Actions helpers, inventory/rotation
├── bootstrap/                      # Scoped Vault policy/OIDC examples
└── tests/                          # Synthetic tests and historical regression fixtures
```

Superseded local-entry/staging wrappers, optional staged Terraform secret-write root, old promotion helper/workflow and duplicate workflow copies were removed. The earlier single-app definition/Terraform root remains for reporting-baseline and OIDC regression tests, not as a second Security workflow. Historical create-only code lives under `tests/fixtures` only.

Customer prerequisites: approved private repository/report access, protected main, reviewer gates, reachable restricted runner, HTTPS/CA trust, exact OIDC bindings and protected per-environment backend. The example uses S3; another protected Terraform backend may be chosen. See [meeting outcomes](MEETING-OUTCOMES.md), [runbook](RUNBOOK.md) and [validation](VALIDATION.md).
