#!/usr/bin/env bash
# Compatibility wrapper for Python reporting; it forwards every argument intact.
# Example: bash 13-Vault-Configuration-Promotion/scripts/vault-drift.sh --env dev --inventory-only
# Offline: invoke this wrapper with --compare /path/dev.json /path/uat.json /path/prod.json.
# Dependencies, identity, JSON output and exits are exactly those of drift.py.
# Resolve the adjacent script independently of the current shell directory; exec
# preserves Python's exit status and signal handling without a wrapper process.
# See SCRIPT-REFERENCE.md. Scheduled Actions calls drift.py directly.

set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/drift.py" "$@"
