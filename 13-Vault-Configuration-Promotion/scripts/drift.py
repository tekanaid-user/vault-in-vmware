#!/usr/bin/env python3
"""Collect read-only inventory or compare existing environment reports.

Used by vault-drift-onboarding.yml and vault-drift.yml. Python 3.10+ and a Git
checkout are required. --env selects environments/<env>/settings.json and the
drift OIDC role; --inventory-only skips the original demo application/release
baseline, but configured inventory expectations still apply. --compare is
offline and expects up to three unique DEV/UAT/PROD JSON reports.
JSON goes to stdout; safe diagnostics go to stderr. Default collection succeeds
when JSON is produced, even with findings. With --fail-on-findings: 0 clean,
1 collection/format error, 2 findings, 3 incomplete evidence. No KV values are
read, no corrections are made. See GETTING-STARTED.md and SCRIPT-REFERENCE.md."""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
import inventory
from common import ApiError, api, app_definition, authenticate, close_token, read_revision, revision, settings


def normalized_policy(text):
    # Tokenize before dropping whitespace/comments; quoted paths remain intact.
    """Normalize policy comments/spacing while preserving whitespace inside strings."""
    tokens = re.findall(r'"(?:\\.|[^"\\])*"|#[^\n]*|//[^\n]*|/\*[\s\S]*?\*/|[^\s"#/]+|[/#]', text)
    return ''.join(token for token in tokens if not token.startswith(('#', '//', '/*')))


def leaf_fields(structure, prefix=''):
    """Flatten nested subkeys to escaped field paths; reject any non-null leaf value."""
    result = []
    for key, value in structure.items():
        name = prefix + key.replace('~', '~0').replace('/', '~1')
        if isinstance(value, dict):
            if value:
                result.extend(leaf_fields(value, name + '/'))
            else:
                result.append(name + '/')
        elif value is None:
            result.append(name)
        else:
            raise ValueError('Subkeys returned a non-null leaf; refusing to serialize it')
    return sorted(result)


def rotation_status(metadata, field, days, today):
    # Never return arbitrary custom metadata, which operators could misuse for secrets.
    """Return only status/age for the chosen ISO date field; never export raw metadata."""
    value = (metadata.get('custom_metadata') or {}).get(field)
    if not value:
        return {'status': 'missing'}
    try:
        date = dt.date.fromisoformat(value)
    except (TypeError, ValueError):
        return {'status': 'invalid'}
    age = (today - date).days
    if age < 0:
        return {'status': 'future_date'}
    return {'status': 'overdue' if age > days else 'current', 'age_days': age}


def collect(env, cfg=None, sha=None, app=None, policy=None, today=None, inventory_only=False):
    """Return one environment report, revoking owned credentials even on failure.

    inventory_only bypasses demo app/release checks. Both modes retain configured
    inventory expectations. cfg/sha/app/policy/today overrides support isolated tests."""
    if inventory_only:
        cfg = cfg or settings(env)
        today = today or dt.datetime.now(dt.timezone.utc).date()
        token, owned = authenticate(cfg, 'drift')
        try:
            snapshot = inventory.scan(cfg, lambda method, path, payload=None: api(cfg, token, method, path, payload),
                                      normalized_policy, leaf_fields, rotation_status, today)
            return {'schema_version': 2, 'environment': env, 'configuration_ref': None,
                    'baseline_mode': 'inventory_only', 'expected': None,
                    'collected_at': dt.datetime.now(dt.timezone.utc).isoformat(),
                    'inventory': snapshot, 'paths': snapshot['kv_paths'],
                    'findings': snapshot['findings'], 'complete': snapshot['complete']}
        finally:
            close_token(cfg, token, owned)
    sha = sha or revision(env)
    app = app or app_definition(sha)
    cfg = cfg or settings(env)
    expected_policy = policy if policy is not None else read_revision(sha, 'policy.hcl.tftpl').decode().replace('${kv_mount}', app['kv_mount']).replace('${secret_path}', app['secret_path'])
    today = today or dt.datetime.now(dt.timezone.utc).date()
    token, owned = authenticate(cfg, 'drift')
    report = {'schema_version': 2, 'environment': env, 'configuration_ref': sha, 'expected': app,
              'collected_at': dt.datetime.now(dt.timezone.utc).isoformat(),
              'paths': {}, 'findings': [], 'complete': True}
    def unknown(kind, path, error):
        report['complete'] = False
        finding = {'kind': kind, 'path': path}
        if isinstance(error, ApiError):
            finding['http_status'] = error.status
        report['findings'].append(finding)
    def read(path):
        return api(cfg, token, 'GET', path)['data']
    try:
        snapshot = inventory.scan(cfg, lambda method, path, payload=None: api(cfg, token, method, path, payload),
                                  normalized_policy, leaf_fields, rotation_status, today)
        report['inventory'] = snapshot
        report['complete'] = snapshot['complete']
        report['findings'].extend(snapshot['findings'])
        mount_prefix = app['kv_mount'].rstrip('/') + '/'
        report['paths'] = {path[len(mount_prefix):]: entry for path, entry in snapshot['kv_paths'].items()
                           if path.startswith(mount_prefix)}
        actual = report['paths'].get(app['secret_path'])
        if actual is None:
            report['findings'].append({'kind': 'not_observed', 'path': app['secret_path'], 'note': 'Check listing failures before declaring missing'})
        elif actual['status'] == 'present':
            expected_fields = set(leaf_fields({key: None for key in app['fields']}))
            missing = sorted(expected_fields - set(actual['fields']))
            extra = sorted(set(actual['fields']) - expected_fields)
            if missing or extra:
                report['findings'].append({'kind': 'field_difference', 'path': app['secret_path'], 'missing': missing, 'extra': extra})
        try:
            actual_policy = read(f"sys/policies/acl/{app['policy_name']}")['policy']
            # Store equality, not the raw policy: unexpected policies could contain sensitive text.
            report['policy_matches_git'] = normalized_policy(actual_policy) == normalized_policy(expected_policy)
            if not report['policy_matches_git']:
                report['findings'].append({'kind': 'policy_difference_from_git'})
        except (ApiError, RuntimeError) as error:
            unknown('policy_unknown', app['policy_name'], error)
        for label, endpoint, expected in (
            ('approle', f"auth/approle/role/{app['approle_name']}", cfg.get('expected_approle')),
            ('kv_config', f"{app['kv_mount']}/config", cfg.get('expected_kv_config')),
        ):
            if expected is None:
                continue
            try:
                live = read(endpoint)
                def normalize(value):
                    return sorted(value) if isinstance(value, list) else value
                differences = [key for key, value in expected.items() if normalize(live.get(key)) != normalize(value)]
                report[label + '_matches_git'] = not differences
                if differences:
                    report['findings'].append({'kind': label + '_difference_from_git', 'fields': sorted(differences)})
            except (ApiError, RuntimeError) as error:
                unknown(label + '_unknown', endpoint, error)
        return report
    finally:
        close_token(cfg, token, owned)


def compare_reports(reports):
    """Compare unique environment artifacts; missing/unknown data yields null parity.

    Return coverage, per-resource differences and findings. A matching inventory
    without an evaluated baseline does not claim Git release/policy compliance."""
    names = {r['environment'] for r in reports}
    if len(names) != len(reports) or not names <= {'dev', 'uat', 'prod'}:
        raise ValueError('Duplicate or invalid environment reports')
    missing = sorted({'dev', 'uat', 'prod'} - names)
    missing_inventory = sorted(r['environment'] for r in reports if 'inventory' not in r)
    complete = not missing and not missing_inventory and all(r.get('complete', False) for r in reports)
    structures = [{p: {k: v for k, v in entry.items() if k != 'rotation'} for p, entry in r.get('inventory', {}).get('kv_paths', r['paths']).items()} for r in reports]
    inventories = {r['environment']: r['inventory'] for r in reports if 'inventory' in r}
    differences, ignored = inventory.compare(inventories) if len(inventories) == len(reports) and inventories else ([], [])
    inventory_complete = complete and len(inventories) == 3
    return {'missing_environment_reports': missing, 'missing_inventory_reports': missing_inventory, 'complete': complete, 'environments': reports,
            'same_selected_release': len({r['configuration_ref'] for r in reports}) == 1 if not missing and all(r.get('configuration_ref') for r in reports) else None,
            'same_observed_structure': len({json.dumps(s, sort_keys=True) for s in structures}) == 1 if complete else None,
            'all_policies_match_selected_git': all(r['policy_matches_git'] for r in reports) if complete and all('policy_matches_git' in r for r in reports) else None,
            'inventory_differences': differences, 'approved_comparison_exceptions': ignored,
            'same_supported_inventory': not differences if inventory_complete else None,
            'has_findings': bool(missing) or bool(missing_inventory) or bool(differences) or any(r['findings'] for r in reports),
            'note': 'Different releases may mean pending promotion. Null parity means incomplete evidence. Values were not read; no corrections or deletions were made.'}


def main():
    """Collect or compare JSON; optionally distinguish findings (2) and incomplete (3)."""
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--env', choices=['dev', 'uat', 'prod'])
    group.add_argument('--compare', nargs='*', metavar='REPORT_JSON')
    parser.add_argument('--fail-on-findings', action='store_true', help='Exit 2 for drift/rotation findings, 3 for incomplete evidence')
    parser.add_argument('--inventory-only', action='store_true', help='Scan without the selected demo application/release.yaml baseline; configured inventory expectations still apply')
    parser.add_argument('--settings-file', type=Path, help='Reviewed environment settings override, e.g. a private localhost lab file; still requires HTTPS/no namespaces')
    args = parser.parse_args()
    if args.inventory_only and not args.env:
        parser.error('--inventory-only requires --env')
    if args.settings_file and not args.env:
        parser.error('--settings-file requires --env')
    try:
        cfg = settings(args.env, filename=args.settings_file) if args.settings_file else None
        report = collect(args.env, cfg=cfg, inventory_only=args.inventory_only) if args.env else compare_reports([json.loads(Path(p).read_text()) for p in args.compare])
        print(json.dumps(report, indent=2))
        if args.fail_on_findings:
            if not report['complete']:
                return 3
            if report.get('has_findings', bool(report.get('findings'))):
                return 2
        return 0
    except Exception:
        print('Drift collection failed; check release, connectivity and read-only permissions', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
