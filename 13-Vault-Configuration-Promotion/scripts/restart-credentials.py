"""Deliberate credential issuance. Deliver only to restricted Vault KV v2."""
import argparse
from common import settings, authenticate, api, ApiError, close_token


def issue(cfg, token, expected_version):
    mount, path = cfg['credential_delivery_mount'], cfg['credential_delivery_path']
    mounts = api(cfg, token, 'GET', 'sys/mounts')['data']
    if mounts.get(mount + '/', {}).get('options', {}).get('version') != '2':
        raise ValueError('Credential delivery mount must already exist as KV v2')
    try:
        version = api(cfg, token, 'GET', f'{mount}/metadata/{path}')['data']['current_version']
    except ApiError as error:
        if error.status != 404:
            raise
        version = 0
    if version != expected_version:
        raise ValueError('Delivery version changed; issuance cancelled')
    role_id = api(cfg, token, 'GET', 'auth/approle/role/restart/role-id')['data']['role_id']
    minted = api(cfg, token, 'POST', 'auth/approle/role/restart/secret-id', {})['data']
    try:
        api(cfg, token, 'POST', f'{mount}/data/{path}', {'options': {'cas': expected_version}, 'data': {'role_id': role_id, 'secret_id': minted['secret_id']}})
    except Exception:
        api(cfg, token, 'POST', 'auth/approle/role/restart/secret-id-accessor/destroy', {'secret_id_accessor': minted['secret_id_accessor']})
        raise RuntimeError('Credential delivery failed; generated SecretID revoked') from None
    return expected_version + 1


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--env', choices=['dev', 'uat', 'prod'], required=True)
    p.add_argument('--expected-version', type=int, required=True)
    args = p.parse_args()
    if args.expected_version < 0:
        raise ValueError('Expected version must be nonnegative')
    cfg = settings(args.env)
    token, owned = authenticate(cfg, 'credential')
    try:
        version = issue(cfg, token, args.expected_version)
        print(f'Credentials delivered to restricted Vault UI path; version {version}. Existing credentials are not revoked.')
    finally:
        close_token(cfg, token, owned)

if __name__ == '__main__':
    main()
