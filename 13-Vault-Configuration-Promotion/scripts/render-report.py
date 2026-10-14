#!/usr/bin/env python3
"""Render comparison and rotation JSON into a readable Markdown report.

Used by vault-drift.yml for report.md and the Actions Summary; runs offline with
no Vault token or network. Arguments: comparison.json rotation-report.json.
Only selected reporting fields are rendered; arbitrary input keys and config
fingerprints are omitted. Table cells escape HTML, pipes and line breaks.
Coverage, per-path field differences, findings, rotation and exceptions are
shown. Exit 0 means rendered successfully; exit 1 means input/render failure.
An incomplete/red report is still useful evidence. See SCRIPT-REFERENCE.md."""
import argparse
import html
import json
from pathlib import Path
import sys


def cell(value):
    """Escape a report field for one Markdown table cell without allowing raw HTML."""
    return html.escape(str(value)).replace('|', '&#124;').replace('\n', ' ').replace('\r', ' ')


def table(headers, rows):
    """Render headers and sanitized rows; an empty section retains its table headers."""
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |',
                      *['| ' + ' | '.join(cell(v) for v in row) + ' |' for row in rows]])


def render(report, rotation):
    """Select coverage/difference/rotation fields; omit arbitrary input data and hashes."""
    sections = ['# Vault drift and rotation report',
                f"Supported scan complete: **{report['complete']}**. Findings: **{report['has_findings']}**.",
                'Read-only report. Differences require review; no corrections or deletions were made. Null Git-baseline results mean the selected application baseline was not evaluated.',
                '## Coverage', table(['Environment', 'Complete', 'Policies', 'KV paths', 'Detail exclusions'],
                    [(r['environment'], r['complete'], len(r['inventory']['policies']),
                      len(r['inventory']['kv_paths']), len(r['inventory']['coverage']['unsupported_details']))
                     for r in report['environments']]),
                'Missing environments: ' + cell(', '.join(report['missing_environment_reports']) or 'none'),
                '## Cross-environment differences',
                table(['Category', 'Resource / application path', 'Different fields', 'DEV', 'UAT', 'PROD'],
                    [(d['category'], d['resource'], ', '.join(d['fields']) or 'resource/status/fingerprint',
                      *[d['environments'].get(env, 'no report') for env in ('dev', 'uat', 'prod')])
                     for d in report['inventory_differences']]),
                'Field names identify differences; inspect per-environment JSON for each environment\'s observed keys. Configuration values and policy text are not shown.',
                '## Environment findings', table(['Environment', 'Kind', 'Path', 'HTTP status'],
                    [(r['environment'], f['kind'], f.get('path', ''), f.get('http_status', ''))
                     for r in report['environments'] for f in r['findings']]),
                '## Rotation findings', table(['Environment', 'Path', 'Status', 'Age (days)'],
                    [(r['environment'], r['path'], r['status'], r.get('age_days', ''))
                     for r in rotation['secrets'] if r['status'] != 'current']),
                'Rotation is based on operator-maintained metadata, not last access. DEV may legitimately lead UAT/PROD.',
                '## Approved exceptions', table(['Category', 'Resource', 'Field', 'Reason'],
                    [(e['category'], e['resource'], e['field'], e['reason'])
                     for e in report['approved_comparison_exceptions']])]
    return '\n\n'.join(sections) + '\n'


def main():
    """Render two local JSON files to stdout; invalid schema/input exits 1 safely."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('comparison', type=Path)
    parser.add_argument('rotation', type=Path)
    args = parser.parse_args()
    try:
        print(render(json.loads(args.comparison.read_text()), json.loads(args.rotation.read_text())), end='')
        return 0
    except Exception:
        print('Report rendering failed; check comparison/rotation format. Details suppressed.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
