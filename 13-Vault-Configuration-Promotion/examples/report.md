> LIVE LOCAL LAB: collected from three real TLS Vault servers with generated non-production data.

# Vault drift and rotation report

Supported scan complete: **True**. Findings: **True**.

Read-only report. Differences require review; no corrections or deletions were made. Null Git-baseline results mean the selected application baseline was not evaluated.

## Coverage

| Environment | Complete | Policies | KV paths | Detail exclusions |
| --- | --- | --- | --- | --- |
| dev | True | 8 | 6 | 1 |
| uat | True | 7 | 4 | 1 |
| prod | True | 7 | 5 | 1 |

Missing environments: none

## Cross-environment differences

| Category | Resource / application path | Different fields | DEV | UAT | PROD |
| --- | --- | --- | --- | --- | --- |
| policies | acl/application-reader | resource/status/fingerprint | present | present | present |
| policies | acl/dev-only | resource/status/fingerprint | present | absent | absent |
| policies | password/application | resource/status/fingerprint | present | present | present |
| auth_methods | local-users/ | external_entropy_access, local, options, seal_wrap, type | present | absent | absent |
| secrets_engines | prototype/ | external_entropy_access, local, options, seal_wrap, type | present | absent | absent |
| configurations | auth/approle/role/example-app | token_ttl | present | present | present |
| configurations | auth/company-ldap/groups/developers | policies | present | present | present |
| configurations | auth/github/role/github-drift | bound_claims/sub | present | present | present |
| configurations | auth/local-users/users/demo-user | token_bound_cidrs, token_explicit_max_ttl, token_max_ttl, token_no_default_policy, token_num_uses, token_period, token_policies, token_ttl, token_type | present | absent | absent |
| configurations | certificates/roles/application | allow_subdomains | present | present | present |
| configurations | encryption/keys/production-only | allow_plaintext_backup, auto_rotate_period, deletion_allowed, derived, exportable, min_decryption_version, min_encryption_version, supports_decryption, supports_derivation, supports_encryption, supports_signing, type | absent | absent | present |
| configurations | prototype/config | cas_required, delete_version_after, max_versions | present | absent | absent |
| configurations | secret/config | max_versions | present | present | present |
| configurations | sys/mounts/auth/local-users/tune | default_lease_ttl, force_no_cache, max_lease_ttl, token_type | present | absent | absent |
| configurations | sys/mounts/prototype/tune | default_lease_ttl, force_no_cache, max_lease_ttl | present | absent | absent |
| configurations | sys/mounts/secret/tune | default_lease_ttl | present | present | present |
| kv_paths | apps/service/config | connection/region | present | present | present |
| kv_paths | secret/example-app-old/config | password, username | present | absent | absent |
| kv_paths | secret/example-app/config | password | present | present | present |
| kv_paths | secret/future-date/config | password | absent | absent | present |
| kv_paths | secret/invalid-date/config | password | present | absent | absent |
| kv_paths | secret/retired/config | password | present | present | deleted |

Field names identify differences; inspect per-environment JSON for each environment's observed keys. Configuration values and policy text are not shown.

## Environment findings

| Environment | Kind | Path | HTTP status |
| --- | --- | --- | --- |
| dev | rotation_missing | secret/example-app-old/config |  |
| dev | rotation_invalid | secret/invalid-date/config |  |
| uat | rotation_overdue | secret/example-app/config |  |
| prod | rotation_future_date | secret/future-date/config |  |
| prod | deleted_path | secret/retired/config |  |

## Rotation findings

| Environment | Path | Status | Age (days) |
| --- | --- | --- | --- |
| dev | secret/example-app-old/config | missing |  |
| dev | secret/invalid-date/config | invalid |  |
| prod | secret/future-date/config | future_date |  |
| uat | secret/example-app/config | overdue | 120 |

Rotation is based on operator-maintained metadata, not last access. DEV may legitimately lead UAT/PROD.

## Approved exceptions

| Category | Resource | Field | Reason |
| --- | --- | --- | --- |
