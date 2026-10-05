#!/usr/bin/env python3
"""Extract rotation age from existing drift artifacts; never connects to Vault."""
import argparse
import json
from pathlib import Path
import sys

STATUSES = {'current', 'overdue', 'missing', 'invalid', 'future_date'}


def build(reports):
    rows = []
    complete = True
    environments = []
    for document in reports:
        for report in document.get('environments', [document]):
            env = report['environment']
            if env not in ('dev', 'uat', 'prod') or env in environments:
                raise ValueError('Duplicate or invalid environment')
            environments.append(env)
            complete = complete and report.get('complete', False)
            for path, entry in report['inventory']['kv_paths'].items():
                rotation = entry.get('rotation', {'status': 'unknown'})
                status = rotation['status']
                if status not in STATUSES | {'unknown'}:
                    raise ValueError('Unexpected rotation status')
                row = {'environment': env, 'path': path, 'status': status}
                if 'age_days' in rotation:
                    age = rotation['age_days']
                    if type(age) is not int or age < 0:
                        raise ValueError('Invalid rotation age')
                    row['age_days'] = age
                rows.append(row)
    missing = sorted({'dev', 'uat', 'prod'} - set(environments))
    return {'complete': complete and not missing, 'missing_environment_reports': missing,
            'counts': {status: sum(r['status'] == status for r in rows) for status in sorted(STATUSES | {'unknown'})},
            'secrets': sorted(rows, key=lambda r: (r['environment'], r['path'])),
            'note': 'Operator-maintained rotation metadata; not proof that the upstream credential rotated. No values or raw metadata included.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reports', nargs='+', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(build([json.loads(p.read_text()) for p in args.reports]), indent=2))
        return 0
    except Exception:
        print('Rotation report failed; check input report format. Details suppressed.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
