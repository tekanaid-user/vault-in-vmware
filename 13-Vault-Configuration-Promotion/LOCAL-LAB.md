# Three real local Vault instances: repeatable validation

This lab creates **three actual Vault Community TLS servers**, seeds different configuration and runs the real Python CLI against them. Reports are API observations, not hand-built JSON. Values are generated non-production test data. The helper only provisions its own localhost instances.

## Start and collect

From repository root with Vault CLI, Python 3.10+ and Git:

```bash
python3 13-Vault-Configuration-Promotion/scripts/local-demo.py start
python3 13-Vault-Configuration-Promotion/scripts/local-demo.py status
python3 13-Vault-Configuration-Promotion/scripts/local-demo.py report
# Repeat: application values are not reseeded by report.
python3 13-Vault-Configuration-Promotion/scripts/local-demo.py report
python3 -m unittest discover -s 13-Vault-Configuration-Promotion/tests -v
```

| Label | Endpoint | Scope |
| --- | --- | --- |
| DEV | `https://127.0.0.1:18520` | Local test instance. |
| UAT | `https://127.0.0.1:18530` | Local test instance. |
| PROD | `https://127.0.0.1:18540` | Local test instance, **not production**. |

Adjacent cluster ports are reserved too. Occupied ports fail safely. `start` is idempotent while all recorded servers run; partial/stale state requires stopping this lab before restart. Existing Vaults on other ports are untouched.

Servers run in Vault **dev mode**, with in-memory data. They remain running after the helper exits until stopped or the host/process restarts. This is a development convenience, not durable storage, HA or recovery evidence. [Official dev-server behavior](https://developer.hashicorp.com/vault/docs/commands/server).

## Credentials and trust

Private runtime state is at `~/.local/state/vault-drift-demo/`: mode-0700 directory, mode-0600 state/credentials/logs, generated TLS CA per instance. Do not share it. It is outside Git; no tokens/private keys enter exported reports. `--state-dir` selects another private directory.

Each instance has private `settings.json` and `vault-ca.pem`. The helper invokes the actual `drift.py --env ENV --inventory-only --settings-file PATH` CLI with its CA and a fresh read-only token, then revokes that token. The optional settings file retains HTTPS/no-namespace validation and avoids changing committed environment definitions.

The UI is available at each URL; trust the generated local CA for this lab. For manual inspection, retrieve only that instance's administrative token from protected `state.json`. Do not paste it into logs, issues, reports or email. Root tokens perform lab bootstrap/control; they are not inventory identities.

## Seeded differences and verification

- ACL/password policies and a DEV-only policy; differing AppRole TTLs and LDAP mappings.
- JWT, LDAP, Kubernetes and AppRole config/roles, plus DEV-only userpass. Directory/cluster URLs are fixtures; their external login integrations are not tested.
- Default/additional/nested KV v2 mounts, tuning/version limits, nested/missing fields, extra paths and soft deletion.
- Transit keys and PKI role settings, without key export or certificate issuance by reporting.
- GitHub issuer trust and exact demonstration-repo/environment bindings. Local inventory uses locally minted read-only tokens; real GitHub federation is tested separately below.
- Current/overdue/missing/invalid/future rotation dates, not inferred last-access dates.
- Actual subkeys reads and **403 value reads** across three KV mounts per environment.
- An actual denied-token scan marked unknown/incomplete, and a missing-environment comparison marked incomplete/null parity.
- Refusal to export seeded test values, root tokens or scan tokens.

[INVENTORY.md](INVENTORY.md) is the coverage contract: raw database connection config, unsupported plugin details, server storage/seal/TLS config and identity entities are excluded. The lab has no preapproved aliases/exceptions; intentional subject differences remain visible.

## Evidence and tests

`report` writes `dev.json`, `uat.json`, `prod.json`, `comparison.json`, `rotation-report.json`, `report.md` and `evidence.json` into `examples/`, or `--output DIR`. Read [the actual report walkthrough](examples/REPORT-WALKTHROUGH.md).

`tests/test_local_demo.py` starts an independent random-port TLS trio in a private temporary directory, verifies CLI collection/repeatability, all five inventory categories, rotation cases, denial handling and credential exclusion, then stops/reaps its own processes. It leaves the operator's lab running. The full suite also covers import/apply, artifact integrity and credential delivery.

## Real GitHub OIDC evidence

The [successful GitHub run](https://github.com/tekanaid-user/vault-in-vmware/actions/runs/38474723943) used **Vault development OIDC pilot**, `runner=isolated`, and an ephemeral container on the development machine. It created its own three disposable TLS Vaults, exchanged signed GitHub identities, rejected an untrusted repository binding, denied values, detected introduced drift and verified Terraform idempotence.

The actual artifact and summary are [oidc-pilot-report.json](examples/oidc-pilot-report.json) and [oidc-evidence.json](examples/oidc-evidence.json). That run used published commit `47ab160`; new local-lab code is separately checked by local tests and recorded as local changes in `evidence.json`.

To reproduce, follow [OIDC-PILOT.md](OIDC-PILOT.md) to build/start one ephemeral runner, then Actions → **Vault development OIDC pilot** → `main` → `isolated`. Local `--local` mode does not prove federation.

A runner on another machine cannot reach this host's loopback endpoints. Recipient reporting requires reachable HTTPS URLs, CA trust and roles bound to **their own** issued claims; follow [GETTING-STARTED.md](GETTING-STARTED.md). Do not copy localhost lab URLs into a remote runner's live settings.

## Stop

```bash
python3 13-Vault-Configuration-Promotion/scripts/local-demo.py stop
```

Only recorded PIDs matching this lab's TLS directory are signalled. Stop removes the active state record; protected logs/certificates remain outside Git. Restart creates new test data because dev-mode data is in memory.
