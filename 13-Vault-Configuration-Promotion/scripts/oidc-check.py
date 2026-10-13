#!/usr/bin/env python3
"""Inspect selected identity claims or test a read-only Vault login; never output tokens."""
import argparse
import base64
import json
import sys
from common import api, authenticate, close_token, github_jwt, settings

CLAIMS = ('iss', 'aud', 'sub', 'repository', 'repository_id', 'repository_owner_id',
          'ref', 'workflow_ref', 'event_name')


def selected_claims(jwt):
    payload = jwt.split('.')[1]
    claims = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))
    # Decoding is diagnostic only. Vault performs signature/issuer/expiry validation.
    return {key: claims[key] for key in CLAIMS if key in claims}


def check(env, claims_only=False):
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
