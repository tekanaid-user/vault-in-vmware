> SYNTHETIC EXAMPLE ONLY: fictitious paths and policies; no live connections or findings.

# Vault drift and rotation report

Supported scan complete: **True**. Findings: **True**.

Read-only report. Differences require review; no corrections or deletions were made. Null Git-baseline results mean the selected application baseline was not evaluated.

## Coverage

| Environment | Complete | Policies | KV paths | Detail exclusions |
| --- | --- | --- | --- | --- |
| dev | True | 1 | 2 | 0 |
| uat | True | 1 | 1 | 0 |
| prod | True | 1 | 1 | 0 |

Missing environments: none

## Cross-environment differences

| Category | Resource / application path | Different fields | DEV | UAT | PROD |
| --- | --- | --- | --- | --- | --- |
| policies | acl/application-reader | resource/status/fingerprint | present | present | present |
| kv_paths | secret/example-app-old/config | password, username | present | absent | absent |
| kv_paths | secret/example-app/config | password | present | present | present |

Field names identify differences; inspect per-environment JSON for each environment's observed keys. Configuration values and policy text are not shown.

## Environment findings

| Environment | Kind | Path | HTTP status |
| --- | --- | --- | --- |
| dev | rotation_missing | secret/example-app-old/config |  |
| uat | rotation_overdue | secret/example-app/config |  |

## Rotation findings

| Environment | Path | Status | Age (days) |
| --- | --- | --- | --- |
| dev | secret/example-app-old/config | missing |  |
| uat | secret/example-app/config | overdue | 120 |

Rotation is based on operator-maintained metadata, not last access. DEV may legitimately lead UAT/PROD.

## Approved exceptions

| Category | Resource | Field | Reason |
| --- | --- | --- | --- |
