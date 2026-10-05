#!/usr/bin/env python3
"""Read-only KV v2 structure/configuration and rotation report. Never GET secret data."""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from common import ApiError, api, app_definition, authenticate, close_token, read_revision, revision, settings


def normalized_policy(text):
    # Tokenize before dropping whitespace/comments; quoted paths remain intact.
    tokens = re.findall(r'"(?:\\.|[^"\\])*"|#[^\n]*|//[^\n]*|/\*[\s\S]*?\*/|[^\s"#/]+|[/#]', text)
    return ''.join(token for token in tokens if not token.startswith(('#', '//', '/*')))


def leaf_fields(structure, prefix=''):
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


def collect(env, cfg=None, sha=None, app=None, policy=None, today=None):
    sha = sha or revision(env)
    app = app or app_definition(sha)
    cfg = cfg or settings(env)
    expected_policy = policy if policy is not None else read_revision(sha, 'policy.hcl.tftpl').decode().replace('${kv_mount}', app['kv_mount']).replace('${secret_path}', app['secret_path'])
    today = today or dt.datetime.now(dt.timezone.utc).date()
    token, owned = authenticate(cfg, 'drift')
    report = {'environment': env, 'configuration_ref': sha, 'expected': app,
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
        def paths(prefix):
            try:
                items = api(cfg, token, 'LIST', f"{app['kv_mount']}/metadata/{prefix}")['data']['keys']
            except (ApiError, RuntimeError) as error:
                unknown('listing_unknown', prefix, error)
                return []
            found = []
            for item in items:
                if not isinstance(item, str) or '..' in item or '/' in item.rstrip('/'):
                    raise ValueError('Unexpected path listing')
                child = prefix + item
                found.extend(paths(child) if item.endswith('/') else [child])
            return found
        scope = cfg.get('drift_prefix', app['secret_path'].rsplit('/', 1)[0] + '/')
        if not scope.endswith('/') or not re.fullmatch(r'[a-zA-Z0-9_/-]+', scope) or '..' in scope:
            raise ValueError('Configure a safe drift_prefix ending in /')
        if not app['secret_path'].startswith(scope):
            raise ValueError('Drift scope must contain the selected application')
        for path in paths(scope):
            entry = {'status': 'unknown'}
            metadata = None
            try:
                metadata = read(f"{app['kv_mount']}/metadata/{path}")
                latest = metadata['versions'][str(metadata['current_version'])]
                deleted = bool(latest['destroyed'] or latest['deletion_time'])
                entry['rotation'] = rotation_status(metadata, cfg.get('rotation_metadata_field', 'password_cycle_date'), cfg.get('rotation_max_age_days', 90), today)
                if entry['rotation']['status'] != 'current':
                    report['findings'].append({'kind': 'rotation_' + entry['rotation']['status'], 'path': path})
                if deleted:
                    entry['status'] = 'deleted'
                    report['findings'].append({'kind': 'deleted_path', 'path': path})
                else:
                    structure = read(f"{app['kv_mount']}/subkeys/{path}")['subkeys']
                    entry.update(status='present', fields=leaf_fields(structure))
            except (ApiError, RuntimeError, KeyError) as error:
                unknown('path_unknown', path, error)
            report['paths'][path] = entry
        actual = report['paths'].get(app['secret_path'])
        if actual is None:
            report['findings'].append({'kind': 'not_observed', 'path': app['secret_path'], 'note': 'Check listing failures before declaring missing'})
        elif actual['status'] == 'present':
            expected_fields = set(leaf_fields({key: None for key in app['fields']}))
            missing = sorted(expected_fields - set(actual['fields']))
            extra = sorted(set(actual['fields']) - expected_fields)
            if missing or extra:
                report['findings'].append({'kind': 'field_difference', 'path': app['secret_path'], 'missing': missing, 'extra': extra})
        for path in report['paths']:
            if path != app['secret_path']:
                report['findings'].append({'kind': 'extra_path', 'path': path, 'note': 'Outside selected Git application; review before classifying as orphan'})
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
    names = {r['environment'] for r in reports}
    if len(names) != len(reports) or not names <= {'dev', 'uat', 'prod'}:
        raise ValueError('Duplicate or invalid environment reports')
    missing = sorted({'dev', 'uat', 'prod'} - names)
    complete = not missing and all(r.get('complete', False) for r in reports)
    structures = [{p: {k: v for k, v in entry.items() if k != 'rotation'} for p, entry in r['paths'].items()} for r in reports]
    return {'missing_environment_reports': missing, 'complete': complete, 'environments': reports,
            'same_selected_release': len({r['configuration_ref'] for r in reports}) == 1 if not missing else None,
            'same_observed_structure': len({json.dumps(s, sort_keys=True) for s in structures}) == 1 if complete else None,
            'all_policies_match_selected_git': all(r.get('policy_matches_git', False) for r in reports) if complete else None,
            'has_findings': bool(missing) or any(r['findings'] for r in reports),
            'note': 'Different releases may mean pending promotion. Null parity means incomplete evidence. Values were not read; no corrections or deletions were made.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--env', choices=['dev', 'uat', 'prod'])
    group.add_argument('--compare', nargs='*', metavar='REPORT_JSON')
    parser.add_argument('--fail-on-findings', action='store_true', help='Exit 2 for drift/rotation findings, 3 for incomplete evidence')
    args = parser.parse_args()
    try:
        report = collect(args.env) if args.env else compare_reports([json.loads(Path(p).read_text()) for p in args.compare])
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
