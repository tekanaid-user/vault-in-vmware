# Workstream 2 onboarding: Vault drift and rotation reporting

**Repository plan:** use one private Git repository for both workstreams. Start with read-only reporting here; add configuration promotion in Workstream 1 once its backend and approval controls are ready. Keep deployment automation disabled during reporting setup.

As agreed, we will start with **Workstream 2: Vault drift and rotation reporting**. The goal is to compare DEV, UAT and PROD so Security can see differences in policies, supported configuration, secret paths and field names, plus missing or overdue rotation dates. The process is read-only: it does not change Vault, copy values between environments or delete anything.

Below is the setup sequence for **your own environments**. Start with DEV, get one successful collection, then repeat for UAT and PROD. **No Terraform or state bucket is needed for this workstream.**

## 1. Start here: which files to open

Open [Section 13 in the repository](https://github.com/tekanaid-user/vault-in-vmware/tree/main/13-Vault-Configuration-Promotion). These are the main entry points:

| File | What you use it for |
| --- | --- |
| [GETTING-STARTED.md](https://github.com/tekanaid-user/vault-in-vmware/blob/main/13-Vault-Configuration-Promotion/GETTING-STARTED.md) | The main setup guide. Follow this first. |
| [HANDOFF.md](https://github.com/tekanaid-user/vault-in-vmware/blob/main/13-Vault-Configuration-Promotion/HANDOFF.md) | A short checklist of responsibilities and the first working session. |
| [examples/report.md — see the output](https://github.com/tekanaid-user/vault-in-vmware/blob/main/13-Vault-Configuration-Promotion/examples/report.md) | The readable report collected from three real local Vaults, showing DEV/UAT/PROD differences and rotation findings. |
| [examples/REPORT-WALKTHROUGH.md](https://github.com/tekanaid-user/vault-in-vmware/blob/main/13-Vault-Configuration-Promotion/examples/REPORT-WALKTHROUGH.md) | Explains each observed difference and how Security should interpret it. |
| [bootstrap/drift-policy.hcl](https://github.com/tekanaid-user/vault-in-vmware/blob/main/13-Vault-Configuration-Promotion/bootstrap/drift-policy.hcl) | The Vault read-only inventory policy for Security to review and install. |
| [bootstrap/github-drift-role.json.example](https://github.com/tekanaid-user/vault-in-vmware/blob/main/13-Vault-Configuration-Promotion/bootstrap/github-drift-role.json.example) | The Vault JWT role template. Replace its placeholders with your own GitHub identity claims. |
| [environments/dev/settings.json](https://github.com/tekanaid-user/vault-in-vmware/blob/main/13-Vault-Configuration-Promotion/environments/dev/settings.json) | Where DEV maps to its Vault URL, authentication mount, audience, role and reporting settings. |
| [.github/workflows/vault-drift-onboarding.yml](https://github.com/tekanaid-user/vault-in-vmware/blob/main/.github/workflows/vault-drift-onboarding.yml) | The first-run workflow: inspect claims, test login, then collect one environment. |
| [.github/workflows/vault-drift.yml](https://github.com/tekanaid-user/vault-in-vmware/blob/main/.github/workflows/vault-drift.yml) | The weekly/on-demand workflow that collects all three environments and produces the combined report. |

The workflows are at the **repository root under .github/workflows**, not inside Section 13. Python runs behind them; Security does not need to operate scripts manually. Leave the admin-deploy, admin-request and credential-issuance workflows for the later promotion workstream.

**Preview the report before setup:** open [the readable output](https://github.com/tekanaid-user/vault-in-vmware/blob/main/13-Vault-Configuration-Promotion/examples/report.md), then [the walkthrough](https://github.com/tekanaid-user/vault-in-vmware/blob/main/13-Vault-Configuration-Promotion/examples/REPORT-WALKTHROUGH.md). For example, the report shows UAT missing a `password` field, an old application path present only in DEV, policy/configuration differences, and overdue or missing rotation metadata. These are real API observations from a controlled local lab with generated non-production data, not findings from your environments. Your run produces the same report format using your own inventory.

## 2. Prepare your repository and GitHub settings — repository administrator

1. Use an approved private repository. Copy Section 13 and the root workflow files, preserving their paths, and have the changes reviewed on `main`.
2. Enable GitHub Actions. Under **Settings → Environments**, create `dev-drift`, `uat-drift` and `prod-drift`. Restrict them to `main` and agree who can launch/review jobs and read reports.
3. Under **Settings → Secrets and variables → Actions → Variables**, keep `VAULT_AUTOMATION_ENABLED=false` and `VAULT_DRIFT_ENABLED=false` during setup. We will enable reporting after the three collections work. No long-lived Vault token needs to be stored in GitHub secrets.

**Expected result:** your repository has the files and the three GitHub job Environments; automation is not yet scheduled against your Vaults.

## 3. Prepare the runner — DevOps / network team

1. Choose an internal Linux machine that can reach all three Vault HTTPS endpoints and GitHub's checkout, identity and artifact services. This is a pipeline runner; the scripts do not need to be installed on application servers.
2. In your repository, go to **Settings → Actions → Runners → New self-hosted runner**. Follow the displayed Linux installation/registration instructions, run it as a service, and add custom label `vault-demo`. Both reporting workflows select this label; if you choose another label, update their `runs-on` settings together.
3. Install **Git and Python 3.10+**. Install the Vault CA chain into system trust, or set `VAULT_CACERT` in the runner service environment to an absolute readable PEM file and restart the service.
4. Confirm the Vault servers can reach GitHub's issuer discovery/signing-key endpoints. This is separate from runner-to-Vault connectivity.

**Expected result:** the runner is **Online** in GitHub with the matching label. A queued job normally means no matching runner is available. Confirm whether your GitHub is Enterprise Cloud or Enterprise Server; issuer/action compatibility can differ.

## 4. Obtain your actual DEV GitHub identity — DevOps, with Security

1. In **your repository**, open **Actions → Vault drift - getting started → Run workflow**.
2. Select branch `main`, environment `dev`, step `claims`, then run.
3. When it finishes, open the run's **Summary → Artifacts**, download `vault-onboarding-dev-claims`, extract the ZIP and open `dev-claims.json`.

**Expected result:** JSON with `iss`, `aud`, `sub`, repository/owner IDs, branch and workflow reference. This step does not contact Vault, so it can run before Vault authentication is configured. Use these exact values from your repo; do not copy the demonstration repo's IDs or subject.

## 5. Configure DEV Vault to trust GitHub — Vault administrator / Security

From an approved workstation with the Vault CLI and a clone of your repository, log in through your approved administrative method. From repository root, set the DEV endpoint/CA and inspect existing authentication methods:

```bash
export VAULT_ADDR='https://YOUR_DEV_VAULT:8200'
export VAULT_CACERT='/absolute/path/to/vault-ca.pem'
vault status
vault auth list
```

If `github/` already exists, check its type/configuration and coordinate changes. For a new mount, enable the **JWT auth method** at that path, configure the issuer from `dev-claims.json`, and install the reviewed policy:

```bash
vault auth enable -path=github jwt
vault write auth/github/config \
  oidc_discovery_url='YOUR_ACTUAL_GITHUB_ISSUER' \
  bound_issuer='YOUR_ACTUAL_GITHUB_ISSUER'
vault policy write github-drift \
  13-Vault-Configuration-Promotion/bootstrap/drift-policy.hcl
```

For the normal public GitHub issuer, both issuer values are `https://token.actions.githubusercontent.com`. Use your actual issuer if different. Review permissions for your mounts, including additional exact rules for nested mount names.

Next, copy the linked **github-drift-role.json.example** to `dev-drift-role.json`. Replace every `CHANGE_ME` value with your repository/owner IDs, exact DEV `sub`, and the two workflow refs in your own repo. Keep `ref=refs/heads/main`; the role permits the onboarding and weekly workflows, and manual/scheduled events. Its audience must match the claims output and settings file. Then install it:

```bash
vault write auth/github/role/github-dev-drift @dev-drift-role.json
```

**Expected result:** DEV Vault has the `github` JWT mount, `github-drift` policy and `github-dev-drift` role. The runner will exchange a short-lived GitHub identity for a scoped Vault token; human LDAP access continues separately.

## 6. Tell the workflow where DEV Vault is — DevOps, reviewed by Security

Edit [environments/dev/settings.json](https://github.com/tekanaid-user/vault-in-vmware/blob/main/13-Vault-Configuration-Promotion/environments/dev/settings.json) in your repository. Keep the full file and update:

- `vault_addr`: your real DEV HTTPS URL.
- `jwt_auth_path`: `github`; `drift_role`: `github-dev-drift`.
- `oidc_audience`: the audience bound in the role; the example uses `vault-demo`.
- `rotation_metadata_field` and `rotation_max_age_days`: agree these with Security; 90 days is an example.
- Initially clear demonstration-only `inventory_expected_fields` and `inventory_resource_aliases` to `{}`, and `inventory_comparison_exceptions` to `[]`. Add your reviewed expectations/exceptions later.

Review and merge these changes to `main` before running. The script reads this JSON file; setting `VAULT_ADDR` on the runner does not override it. Vault Community Edition uses separate endpoints, with no namespaces.

## 7. Test DEV login, then collect DEV — Security, with DevOps support

1. Run **Vault drift - getting started** again with `dev / authenticate`. Download `vault-onboarding-dev-authenticate` and open `dev-authentication.json`. Expect `authenticated: true` and an engine count.
2. Run the same workflow with `dev / collect`. Download `vault-onboarding-dev-collect` and open `dev.json`.
3. Review `complete`, `findings`, `inventory.kv_paths` and `inventory.coverage.unsupported_details`. A green collection job means it produced JSON; it does not mean there are no differences or gaps.

**Expected result:** a DEV inventory showing paths/field names and supported configuration without secret values. If `complete=false`, resolve the failed/denied reads before treating the scan as complete. Missing rotation metadata is a finding, not a pipeline setup failure.

## 8. Repeat for UAT and PROD — same teams, through the required change processes

Repeat claims, Vault trust/policy/role setup, endpoint settings, authentication and collection separately:

| Environment | Settings file | Vault role | GitHub Environment |
| --- | --- | --- | --- |
| UAT | [uat/settings.json](https://github.com/tekanaid-user/vault-in-vmware/blob/main/13-Vault-Configuration-Promotion/environments/uat/settings.json) | `github-uat-drift` | `uat-drift` |
| PROD | [prod/settings.json](https://github.com/tekanaid-user/vault-in-vmware/blob/main/13-Vault-Configuration-Promotion/environments/prod/settings.json) | `github-prod-drift` | `prod-drift` |

Use each environment's own endpoint and exact issued subject. Keep the policy/audience consistent where intended. **Expected result:** three independently reviewed, complete supported inventories.

## 9. Produce the combined report and enable weekly reporting — repository administrator + Security

1. Set repository variable `VAULT_DRIFT_ENABLED=true`. Keep `VAULT_AUTOMATION_ENABLED=false` so reporting does not enable deployment/credential workflows.
2. Open **Actions → Weekly Vault inventory and rotation → Run workflow → main**.
3. Read the report tables in **Summary**. Download `vault-drift-comparison` and extract `report.md`, `comparison.json` and `rotation-report.json`. Individual `vault-drift-dev/uat/prod` artifacts contain the source inventories.

**Use the examples while reviewing your first run:** [report.md](https://github.com/tekanaid-user/vault-in-vmware/blob/main/13-Vault-Configuration-Promotion/examples/report.md) shows the readable tables; [REPORT-WALKTHROUGH.md](https://github.com/tekanaid-user/vault-in-vmware/blob/main/13-Vault-Configuration-Promotion/examples/REPORT-WALKTHROUGH.md) explains how to interpret differences. The corresponding [comparison JSON](https://github.com/tekanaid-user/vault-in-vmware/blob/main/13-Vault-Configuration-Promotion/examples/comparison.json) and [rotation JSON](https://github.com/tekanaid-user/vault-in-vmware/blob/main/13-Vault-Configuration-Promotion/examples/rotation-report.json) show the downloadable data format. Compare the layout and meaning, not the lab's particular paths or counts.

The schedule is **once a week, Mondays at 11:00 UTC**; manual runs remain available. Artifacts are retained seven days. The final report job can be red while the report is successfully saved: exit **2** means findings to review; exit **3** means incomplete evidence to fix.

**What to expect:** paths/keys or policies missing/different across environments; changed supported configuration; missing/old/invalid rotation metadata. Values are expected to differ and are not compared. DEV may legitimately lead UAT/PROD. Security classifies findings as pending promotion, intended exceptions, mistakes or cleanup candidates; no automatic correction/deletion occurs. Unused-path cleanup needs available audit history and application-owner confirmation.

I suggest our first working session takes us through **steps 2–7 for DEV**, with the repository/runner owner and Vault administrator present. Once DEV is working, the same checklist guides the team through UAT and PROD independently.
