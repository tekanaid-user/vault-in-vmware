# Workstream 2: inventory, drift and rotation

Security reviews **Actions → Weekly Vault inventory and rotation**. It scans DEV/UAT/PROD independently, compares the inventories and saves `comparison.json` plus `rotation-report.json`. No corrections or deletions occur.

## Coverage

| Area | Collected and compared |
| --- | --- |
| Policies | All ACL and password policies; normalized content fingerprint; built-in root recorded without fetching it. Vault Community scope; Sentinel policies are not applicable. |
| Auth methods | Every enabled mount/type/options and supported tuning fields. AppRole, JWT/OIDC, Kubernetes and token roles; LDAP config/group/user mappings; userpass policy/TTL settings; GitHub org/team/user mappings. |
| Secrets engines | Every enabled mount/type/options and supported tuning fields. KV v2 config; transit key settings; PKI URLs/CRL/roles; database role TTL/type/rotation settings. |
| KV v2 | Every accessible mount, recursive metadata-root listing, live/deleted/metadata-only paths, nested keys via [Read Secret Subkeys](https://developer.hashicorp.com/vault/api-docs/secret/kv/kv-v2#read-secret-subkeys). No data endpoint or value comparison. Empty objects and scalar/array leaves can appear as `null` in subkeys; this is a key-shape check, not full type validation. |
| Git baseline | Selected application's fields, ACL policy, AppRole settings and KV config; explicit per-environment `inventory_expected_fields`, including exact runner JWT subjects. Full inventory parity does not replace modelling every application's desired configuration in Git. |
| Rotation | Every scanned KV path: current, overdue, missing, invalid or future date and age in days. Default custom metadata `password_cycle_date`, ISO `YYYY-MM-DD`, 90-day threshold must be agreed with Security. |

**Supported coverage is explicit.** Other plugin details are listed under `coverage.unsupported_details`; common mount settings remain compared. Credential fields, KV v1 data, database connection strings/statements, secret issuance/export, identity entities/groups and server storage/seal/TLS settings are excluded. Run against each independent DEV/UAT/PROD Vault Community instance; namespaces are not used. Allowlists are maintained in `scripts/inventory.py`; incompatible versions/denied reads remain unknown.

## Permissions and comparison rules

| Rule | Implementation |
| --- | --- |
| Restricted identity | `bootstrap/drift-policy.hcl`: list/read configuration, metadata/subkeys; no KV data or credential generation. `sys/capabilities-self` uses a read-only POST to distinguish permitted empty collections from denied/hidden listings. Revoke-self is the only lifecycle write. |
| Nested mounts | The sample `+` rules cover single-segment mounts. Add exact metadata/subkeys/config/tune and auth-adapter rules for nested mount names; unresolved access makes the report incomplete. |
| No content in artifacts | Only allowlisted configuration fingerprints, policy fingerprints, names, key structure and rotation status/age are serialized. Credentials, raw configuration/policies/custom metadata are omitted. Names and fingerprints still require protected report access. |
| Expected differences | Reviewed `inventory_resource_aliases` normalizes exact resource names; `inventory_comparison_exceptions` identifies an exact field and reason and must match in all three reports. No blanket environment-name substitutions. |
| OIDC safety | Only environment subject is excepted from cross-environment parity; `inventory_expected_fields` checks each actual subject against its own Git definition. Repository/ref/workflow binding changes remain compared. |
| Meaning of complete | All requested **supported** endpoints completed in each Vault Community instance. It does not mean every plugin setting is supported. Unknown paths or missing environment reports produce null parity and exit 3. Findings/differences produce exit 2 with `--fail-on-findings`. |

```bash
# Authenticate separately to each target using a restricted identity.
./scripts/vault-drift.sh --env dev > dev.json
./scripts/vault-drift.sh --env uat > uat.json
./scripts/vault-drift.sh --env prod > prod.json
./scripts/vault-drift.sh --compare dev.json uat.json prod.json > comparison.json
python3 scripts/rotation-report.py comparison.json > rotation-report.json
```

Rotation reads only the configured custom-metadata date. Missing dates require follow-up; a KV update is not proof of credential rotation. The report neither rotates credentials nor assumes applications reload them automatically. Agree the operational rotation procedure with application owners.

Sources: [auth inventory](https://developer.hashicorp.com/vault/api-docs/system/auth), [engine inventory/tuning](https://developer.hashicorp.com/vault/api-docs/system/mounts), [policies](https://developer.hashicorp.com/vault/api-docs/system/policies), [password policies](https://developer.hashicorp.com/vault/api-docs/system/policies-password), [capability introspection](https://developer.hashicorp.com/vault/api-docs/system/capabilities-self).
