#!/usr/bin/env python3
"""Inspect selected GitHub identity claims or prove a scoped Vault login.

Used by vault-drift-onboarding.yml; choose --env dev|uat|prod. --claims-only
requests a JWT using the configured audience and emits only selected non-secret
claims, without contacting Vault or validating the signature. Without that flag,
requires GitHub Actions, exchanges the JWT using drift_role, reads sys/mounts,
and revokes the owned token. A local CLI token cannot substitute for federation.
Outputs JSON to stdout, suppressed failure diagnostics to stderr; exits 0/1.
This checks login/mount access, not full scan coverage or secret-data denial.
See GETTING-STARTED.md and SCRIPT-REFERENCE.md."""
import argparse
import base64
import json
import sys
from common import api, authenticate, close_token, github_jwt, settings

CLAIMS = ('iss', 'aud', 'sub', 'repository', 'repository_id', 'repository_owner_id',
          'ref', 'workflow_ref', 'event_name')


def selected_claims(jwt):
    """Decode and select diagnostic claims only; this does not validate JWT authenticity."""
    payload = jwt.split('.')[1]
    claims = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))
    # Decoding is diagnostic only. Vault performs signature/issuer/expiry validation.
    return {key: claims[key] for key in CLAIMS if key in claims}


def check(env, claims_only=False):
    """Return claims without Vault access, or test Actions login and sys/mounts read.

    The authentication branch rejects local-token fallback and always closes owned
    tokens. It proves only the operations performed here, not full inventory access."""
    cfg = settings(env, live=not claims_only)
    if claims_only:
        return {'mode': 'claims inspection; not a Vault authentication test',
                'claims': selected_claims(github_jwt(cfg['oidc_audience']))}
    # Refuse the local CLI token fallback: this check must prove GitHub federation.
    import os
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise ValueError('Authentication check requires GitHub Actions')
    token, owned = authenticate(cfg, 'drift')
    try:
        mounts = api(cfg, token, 'GET', 'sys/mounts')['data']
        return {'mode': 'GitHub OIDC to Vault', 'environment': env,
                'authenticated': True, 'secrets_engine_count': len(mounts),
                'note': 'Login and mount-read check only; run collection to verify full coverage.'}
    finally:
        close_token(cfg, token, owned)


def main():
    """Emit a safe JSON check result (0) or suppressed failure diagnostic (1)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env', required=True, choices=['dev', 'uat', 'prod'])
    parser.add_argument('--claims-only', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(check(args.env, args.claims_only), indent=2))
        return 0
    except Exception:
        print('OIDC check failed; check job permissions, settings, TLS and exact Vault role bindings. Tokens/responses suppressed.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
