"""Actions-only non-secret form -> reviewable Git change. No Vault writes."""
import argparse
import ipaddress
import json
import re
import subprocess
from common import BASE, REPO, PREFIX

DEFAULT = dict(secret_id_ttl=86400, secret_id_num_uses=150, token_ttl=18000,
               token_max_ttl=86400, token_num_uses=100, token_bound_cidrs=[],
               secret_id_bound_cidrs=[], token_no_default_policy=False)

def names(raw):
    result = raw.split()
    if not result or len(set(result)) != len(result):
        raise ValueError('Provide unique application names')
    if any(not re.fullmatch(r'[a-z][a-z0-9_-]{0,62}', x) or x in ('restart', 'root', 'default') for x in result):
        raise ValueError('Invalid or reserved application name')
    return result

def settings(raw, defaults):
    supplied = json.loads(raw)
    if not isinstance(supplied, dict) or set(supplied) - set(DEFAULT):
        raise ValueError('Only documented non-secret AppRole settings are accepted')
    result = defaults | supplied
    for k, v in result.items():
        if k.endswith('_cidrs'):
            if not isinstance(v, list):
                raise ValueError('CIDRs must be an array')
            for cidr in v:
                ipaddress.ip_network(cidr, strict=True)
        elif k == 'token_no_default_policy':
            if type(v) is not bool:
                raise ValueError('Expected boolean')
        elif type(v) is not int or v < 0 or v > 31536000:
            raise ValueError('TTL/count must be a nonnegative integer within limits')
    if result['token_max_ttl'] and result['token_ttl'] > result['token_max_ttl']:
        raise ValueError('Token TTL exceeds maximum')
    return result

def generate(args):
    selected = names(args.applications)
    if not re.fullmatch(r'[A-Za-z0-9 _./:#-]{1,120}', args.ticket):
        raise ValueError('Provide a non-secret change ticket reference')
    catalog_path = BASE / 'configuration/admin-catalog.json'
    catalog = json.loads(catalog_path.read_text())
    if args.operation == 'configure':
        fields = args.keys.split()
        if not fields or len(set(fields)) != len(fields) or any(not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', x) for x in fields):
            raise ValueError('Provide unique field names only')
        if args.setup_mode == 'restart':
            if set(selected) - set(catalog['applications']):
                raise ValueError('Restart-only setup requires existing catalog applications')
        else:
            for name in selected:
                catalog['applications'][name] = {'fields': fields, 'settings': settings(args.application_settings, DEFAULT)}
        if args.setup_mode in ('restart', 'both'):
            catalog['restart_settings'] = settings(args.restart_settings, catalog['restart_settings'])
        return catalog_path, catalog
    if not re.fullmatch(r'[0-9a-f]{40}', args.configuration_ref) or args.configuration_ref == '0' * 40:
        raise ValueError('Promotion requires a full reviewed main commit SHA')
    subprocess.run(['git', 'merge-base', '--is-ancestor', args.configuration_ref, 'origin/main'], cwd=REPO, check=True)
    pinned = json.loads(subprocess.check_output(['git', 'show', f'{args.configuration_ref}:{PREFIX}/configuration/admin-catalog.json'], cwd=REPO))
    if set(selected) - set(pinned['applications']):
        raise ValueError('Applications must exist in the reviewed catalog')
    target = BASE / 'environments' / args.environment / 'admin-release.json'
    old = json.loads(target.read_text())
    # A release describes the full managed set. Never silently drop existing apps/restart.
    combined = sorted(set(old['applications']) | set(selected))
    if set(combined) - set(pinned['applications']):
        raise ValueError('Pinned catalog is missing previously managed applications')
    modes = {old['setup_mode'], args.setup_mode} if old['configuration_ref'] != '0'*40 else {args.setup_mode}
    mode = 'both' if 'both' in modes or modes == {'applications', 'restart'} else args.setup_mode
    return target, {'configuration_ref': args.configuration_ref, 'setup_mode': mode, 'applications': combined}

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--operation', choices=['configure', 'promote'], required=True)
    p.add_argument('--environment', choices=['dev', 'uat', 'prod'], required=True)
    p.add_argument('--setup-mode', choices=['applications', 'restart', 'both'], required=True)
    p.add_argument('--applications', required=True)
    p.add_argument('--keys', default='api-key db-password')
    p.add_argument('--application-settings', default='{}')
    p.add_argument('--restart-settings', default='{}')
    p.add_argument('--configuration-ref', default='')
    p.add_argument('--ticket', required=True)
    args = p.parse_args()
    path, content = generate(args)
    path.write_text(json.dumps(content, indent=2, sort_keys=True) + '\n')
    print(path.relative_to(REPO))

if __name__ == '__main__':
    main()
