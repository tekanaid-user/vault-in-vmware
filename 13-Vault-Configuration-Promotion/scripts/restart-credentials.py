"""Issue a restart SecretID and deliver it directly to a restricted KV v2 path.

Called only by vault-restart-credentials.yml with --env and --expected-version
(nonnegative; 0 for first delivery). Uses credential_role, an existing restart
AppRole and an existing restricted credential_delivery_mount/path. Checks the
current version before minting and uses CAS on delivery. A failed delivery
attempts to destroy the newly minted SecretID accessor; cleanup failure requires
administrator investigation. This operation writes a credential, unlike drift.
Prints only delivery version; it does not revoke previously issued credentials.
Owned authentication tokens are revoked. See RUNBOOK.md and SCRIPT-REFERENCE.md."""
import argparse
from common import settings, authenticate, api, ApiError, close_token


def issue(cfg, token, expected_version):
    """Return the new delivery version after a checked, CAS-protected credential write.

    On write failure, revoke the newly minted accessor; report cleanup failure for
    manual investigation. Previously valid SecretIDs are deliberately retained."""
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
        try:
            api(cfg, token, 'POST', 'auth/approle/role/restart/secret-id-accessor/destroy', {'secret_id_accessor': minted['secret_id_accessor']})
        except Exception:
            raise RuntimeError('Credential delivery and cleanup failed; administrator must investigate issuance in Vault audit logs') from None
        raise RuntimeError('Credential delivery failed; generated SecretID revoked') from None
    return expected_version + 1


def main():
    """Select environment and expected version; authenticate with credential_role only."""
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
