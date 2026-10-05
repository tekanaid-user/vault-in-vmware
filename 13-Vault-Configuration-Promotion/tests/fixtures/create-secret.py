#!/usr/bin/env python3
"""Create a new KV v2 secret directly with approved Git fields and hidden prompts."""
import argparse
import getpass
import sys
import warnings
from common import api, app_definition, authenticate, close_token, revision, settings


def create(cfg, token, app, values):
    if set(values) != set(app['fields']) or any(not isinstance(v, str) or not v for v in values.values()):
        raise ValueError('Supply all approved fields; blank values are not accepted')
    # CAS=0 never overwrites an existing location, including a soft-deleted one.
    api(cfg, token, 'POST', f"{app['kv_mount']}/data/{app['secret_path']}", {'options': {'cas': 0}, 'data': values})
    actual = api(cfg, token, 'GET', f"{app['kv_mount']}/subkeys/{app['secret_path']}")['data']['subkeys']
    if set(actual) != set(app['fields']) or any(v is not None for v in actual.values()):
        raise ValueError('Created, but post-write structure verification failed; investigate without retrying writes')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env', choices=['dev', 'uat', 'prod'], required=True)
    parser.add_argument('--approve-environment', required=True)
    args = parser.parse_args()
    token = None
    try:
        if not sys.stdin.isatty() or args.approve_environment != args.env:
            raise ValueError('Interactive terminal and exact environment approval required')
        cfg = settings(args.env)
        app = app_definition(revision(args.env))
        token, owned = authenticate(cfg)
        print(f"Create only: {args.env} / {cfg['vault_addr']} / {app['kv_mount']}/{app['secret_path']}")
        warnings.simplefilter('error', getpass.GetPassWarning)
        values = {field: getpass.getpass(f'{field} (hidden): ') for field in app['fields']}
        create(cfg, token, app, values)
        print('Created and verified field names. Values were not printed. Later value edits use the Vault UI.')
        return 0
    except Exception:
        print('Creation failed; check approved schema, permissions and whether the path already exists. Response suppressed.', file=sys.stderr)
        return 1
    finally:
        if token:
            close_token(cfg, token, owned)


if __name__ == '__main__':
    sys.exit(main())
