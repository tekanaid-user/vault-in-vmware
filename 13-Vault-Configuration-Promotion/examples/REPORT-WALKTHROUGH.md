# Read the first report

These files are **synthetic examples**, generated with the actual Python comparison, rotation and Markdown-rendering functions. Application names are fictitious. They were not collected from any live Vault.

Start with [the readable report](report.md). The machine-readable equivalents are [comparison.json](comparison.json) and [rotation-report.json](rotation-report.json).

| Example finding | Evidence shown | Security's next step |
| --- | --- | --- |
| The example application's `password` field differs | `secret/example-app/config` exists in all three environments. DEV/PROD show `password, username`; UAT shows only `username`. The comparison identifies `password` as the differing field. | Check the application's required fields and approved ticket. Values are not compared or displayed. |
| Extra DEV path from an old name | `secret/example-app-old/config` exists in DEV and is absent in UAT/PROD. | Investigate rename/project history and application ownership. Query available Splunk audit history before considering cleanup. It is a candidate, not an approved deletion. |
| Policy difference | `acl/application-reader` exists everywhere but its policy fingerprint differs in UAT. | Have Security inspect and compare the live policies using approved administrative access. Raw policy text is deliberately not exported. |
| Overdue rotation | UAT example-app metadata reports age 120 days; sample threshold is 90. | Confirm the date represents an actual upstream credential rotation; coordinate with application owners. |
| Missing rotation date | DEV's old-name path has no usable date. | Identify its owner and record the actual rotation date; do not substitute the last-write timestamp. |

This sample has `complete: true` and `has_findings: true`; the scheduled workflow would save the report and finish with **exit 2**. The single-environment onboarding collector stays green if it can produce JSON, even when that JSON contains findings.

If an environment cannot be collected, `missing_environment_reports` names it, `complete` becomes false and parity fields become `null`; the comparison job finishes with **exit 3**. If a policy/listing read is denied, the environment includes an unknown finding with its HTTP status. That is incomplete evidence, not a missing resource or a clean comparison.

`same_selected_release` and `all_policies_match_selected_git` are `null` in inventory-only mode. Policy/configuration comparisons still occur across environments; an approved Git application baseline was not checked. Review `inventory.coverage.unsupported_details` and `approved_comparison_exceptions` as well as the headline result.

## Where the files appear in Actions

Open the run's **Summary** for the readable tables. Download artifact **vault-drift-comparison** for `report.md`, `comparison.json` and `rotation-report.json`. Download **vault-drift-dev**, **vault-drift-uat** and **vault-drift-prod** for per-environment observed field names and coverage details. Retention is seven days.

To regenerate Markdown from downloaded JSON, from repository root:

```bash
python3 13-Vault-Configuration-Promotion/scripts/render-report.py \
  comparison.json rotation-report.json > report.md
```

The renderer only selects reporting fields; it never connects to Vault. No last-access report or cleanup automation is implemented.
