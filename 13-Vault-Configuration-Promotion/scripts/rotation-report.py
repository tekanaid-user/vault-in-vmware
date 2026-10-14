#!/usr/bin/env python3
"""Build an offline rotation-age report from existing inventory artifacts.

Called by vault-drift.yml after comparison. Positional inputs are JSON collector
reports or comparison documents; no Vault access, credentials or network needed.
Outputs sorted environment/path/status/age rows and counts to stdout. Missing
environments or incomplete scans keep complete=False. Dates are operator
metadata, not proof of upstream rotation or last access. Current, overdue,
missing, invalid, future_date and unknown are counted; raw metadata is omitted.
Exit 0 means a report was produced, not that rotation findings are absent;
exit 1 means invalid input. See SCRIPT-REFERENCE.md."""
import argparse
import json
from pathlib import Path
import sys

STATUSES = {'current', 'overdue', 'missing', 'invalid', 'future_date'}


def build(reports):
    """Aggregate unique environment reports into sanitized rotation rows and counts.

    Accept collector documents or comparison documents. Missing environments make
    complete=False, while unexpected statuses/ages and duplicate environments fail."""
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
    """Read local JSON inputs and emit rotation JSON; never authenticate to Vault."""
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
