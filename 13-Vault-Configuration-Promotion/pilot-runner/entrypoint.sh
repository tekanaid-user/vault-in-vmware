#!/usr/bin/env bash
# Container entrypoint, not an operator's host-side setup command.
# start.py supplies RUNNER_REGISTRATION_TOKEN and RUNNER_NAME; the Docker image
# already contains a pinned Actions runner. Registration is deliberately bound
# to the demonstration repo and vault-pilot label, not a live deployment runner.
# --ephemeral accepts one job; --disableupdate relies on rebuilding the pinned
# image for upgrades. Unset the registration token before exec starts the agent.
# The container is launched with --rm; interrupted runs may need offline runner
# registration cleanup. See OIDC-PILOT.md and SCRIPT-REFERENCE.md.

set -euo pipefail
cd /opt/actions-runner
./config.sh --unattended --url https://github.com/tekanaid-user/vault-in-vmware \
  --token "$RUNNER_REGISTRATION_TOKEN" --name "$RUNNER_NAME" \
  --labels vault-pilot --ephemeral --disableupdate --work _work
unset RUNNER_REGISTRATION_TOKEN
exec ./run.sh
