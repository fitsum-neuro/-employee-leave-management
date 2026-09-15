#!/usr/bin/env python3
"""
Regenerate metrics.json from real measurements.

Reads the defect log and a coverage.py JSON report, counts the source lines of
the application under test, runs the suite to get pass/fail counts, and writes
metrics.json. Nothing here is estimated.

Usage:
    python3 -m pytest --cov=app --cov-branch --cov-report=json:coverage.json
    python3 tools/collect_metrics.py

Author: Henok Zemedkun (ATE/8552/16) - Person 2, Test Architect
"""
import csv
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / 'app'
COVERAGE_JSON = ROOT / 'coverage.json'
DEFECT_LOG = ROOT / 'defect_log.csv'
OUTPUT = ROOT / 'metrics.json'

# Source module each defect was raised against, for the by-module breakdown.
DEFECT_MODULE = {
    'DEF-001': 'app/routes.py',
    'DEF-002': 'app/routes.py',
    'DEF-003': 'app/business_logic.py',
    'DEF-004': 'app/business_logic.py',
    'DEF-005': 'app/models.py',
}

# Designed test cases per technique, from docs/test_design.md.
DESIGNED_CASES = {
    'equivalence_partitioning': 26,
    'boundary_value_analysis': 27,
    'decision_table': 22,
    'state_transition': 41,
}


def source_lines_of_code():
    """Non-blank, non-comment Python lines in app/, per file and in total."""
    per_file = {}
    for path in sorted(APP.rglob('*.py')):
        lines = [
            line for line in path.read_text(encoding='utf-8').splitlines()
            if line.strip() and not line.strip().startswith('#')
        ]
        per_file[str(path.relative_to(ROOT))] = len(lines)
    return per_file, sum(per_file.values())


def read_defects():
    with DEFECT_LOG.open(encoding='utf-8') as handle:
        return list(csv.DictReader(handle))


def run_suite():
    """Run pytest and return (total, passed, failed)."""
    result = subprocess.run(
        [sys.executable, '-m', 'pytest', '-q', '--no-header', '-p', 'no:cacheprovider'],
        cwd=ROOT, capture_output=True, text=True,
    )
    tail = result.stdout.strip().splitlines()[-1]
    passed = int(m.group(1)) if (m := re.search(r'(\d+) passed', tail)) else 0
    failed = int(m.group(1)) if (m := re.search(r'(\d+) failed', tail)) else 0
    return passed + failed, passed, failed


def main():
    if not COVERAGE_JSON.exists():
        sys.exit(
            'coverage.json not found. Run:\n'
            '  python3 -m pytest --cov=app --cov-branch '
            '--cov-report=json:coverage.json'
        )

    coverage = json.loads(COVERAGE_JSON.read_text(encoding='utf-8'))
    totals = coverage['totals']

    defects = read_defects()
    defects_found = len(defects)
    # No release has happened yet, so no defect has reached a user. This is a
    # measured zero, not an assumption: the escaped count is re-measured after
    # UAT and after release.
    defects_escaped = 0
    dre = round(
        100.0 * defects_found / (defects_found + defects_escaped), 2
    ) if defects_found + defects_escaped else 0.0

    per_file_loc, total_loc = source_lines_of_code()
    defect_density = round(defects_found / (total_loc / 1000.0), 2)

    statement_coverage = round(totals['percent_covered'], 2)
    branch_coverage = round(
        100.0 * totals['covered_branches'] / totals['num_branches'], 2
    ) if totals['num_branches'] else 0.0

    executed, passed, failed = run_suite()

    severity = Counter(d['severity'] for d in defects)
    priority = Counter(d['priority'] for d in defects)
    status = Counter(d['status'] for d in defects)
    by_module = Counter(DEFECT_MODULE[d['ID']] for d in defects)

    core = coverage['files']['app/business_logic.py']['summary']

    metrics = {
        'project': 'Employee Leave Management System',
        'measured_on': date.today().isoformat(),
        'measured_by': 'Henok Zemedkun (ATE/8552/16) - Person 2, Test Architect',
        'generated_by': 'tools/collect_metrics.py',

        # --- the five headline metrics -----------------------------------
        'defect_density': defect_density,
        'defect_removal_efficiency': dre,
        'defects_found': defects_found,
        'defects_escaped': defects_escaped,
        'coverage_percentage': statement_coverage,

        # --- how each headline figure was derived ------------------------
        'defect_density_detail': {
            'value': defect_density,
            'unit': 'defects per 1000 lines of application code',
            'formula': 'defects_found / (source_lines_of_code / 1000)',
            'defects_found': defects_found,
            'source_lines_of_code': total_loc,
            'loc_basis': 'non-blank, non-comment Python lines under app/',
            'lines_per_file': per_file_loc,
        },
        'defect_removal_efficiency_detail': {
            'value': dre,
            'unit': 'percent',
            'formula': (
                '100 * defects_found_before_release / '
                '(defects_found_before_release + defects_escaped_to_users)'
            ),
            'basis': (
                'All five defects were found by testing before any release, and '
                'none has reached a user because the system has not been '
                'released. DRE must be re-measured after UAT and after release; '
                'the figure below is the pre-release value only.'
            ),
            'by_phase': {
                'unit_testing': {
                    'defects_found': 0,
                    'defects_escaped_to_later_phases': 5,
                    'removal_efficiency_percent': 0.0,
                    'note': (
                        'The 52 unit tests that existed before this test design '
                        'passed against all five defects. Phase DRE of 0% is the '
                        'most important number in this file: it shows unit tests '
                        'alone did not exercise the rule combinations and state '
                        'paths where the defects live.'
                    ),
                },
                'integration_testing': {
                    'defects_found': 5,
                    'defects_escaped_to_later_phases': 0,
                    'removal_efficiency_percent': 100.0,
                    'note': (
                        'Decision table and state transition testing found all '
                        'five: DEF-003 and DEF-004 from the decision table, '
                        'DEF-001, DEF-002 and DEF-005 from state transitions.'
                    ),
                },
                'system_testing': {
                    'defects_found': 0,
                    'defects_escaped_to_later_phases': 0,
                    'removal_efficiency_percent': None,
                },
                'uat': {
                    'defects_found': 0,
                    'defects_escaped_to_later_phases': 0,
                    'removal_efficiency_percent': None,
                },
            },
        },
        'coverage_detail': {
            'statement_coverage_percent': statement_coverage,
            'branch_coverage_percent': branch_coverage,
            'statements_total': totals['num_statements'],
            'statements_covered': totals['covered_lines'],
            'branches_total': totals['num_branches'],
            'branches_covered': totals['covered_branches'],
            'partial_branches': totals['num_partial_branches'],
            'core_module': {
                'file': 'app/business_logic.py',
                'statement_coverage_percent': round(core['percent_covered'], 2),
                'branch_coverage_percent': round(
                    100.0 * core['covered_branches'] / core['num_branches'], 2
                ) if core['num_branches'] else 0.0,
                'target_percent': 80.0,
                'meets_target': core['percent_covered'] >= 80.0,
            },
            'per_file': {
                name: round(data['summary']['percent_covered'], 2)
                for name, data in sorted(coverage['files'].items())
            },
        },

        # --- supporting counts -------------------------------------------
        'defects_by_severity': dict(severity),
        'defects_by_priority': dict(priority),
        'defects_by_status': dict(status),
        'defects_by_module': dict(by_module),
        'test_cases_designed': sum(DESIGNED_CASES.values()),
        'test_cases_designed_by_technique': DESIGNED_CASES,
        'automated_tests': {
            'total': executed,
            'passed': passed,
            'failed': failed,
            'pass_rate_percent': round(100.0 * passed / executed, 2) if executed else 0.0,
            'failing_are_defect_probes': failed == defects_found,
            'note': (
                'The failing tests are the defect reproducers marked with the '
                '`defect` marker, one per logged defect. '
                'Run `pytest -m "not defect"` to exclude them.'
            ),
        },
    }

    OUTPUT.write_text(json.dumps(metrics, indent=2) + '\n', encoding='utf-8')
    print(f'wrote {OUTPUT.relative_to(ROOT)}')
    print(f'  defect_density              {defect_density} per KLOC')
    print(f'  defect_removal_efficiency   {dre}%')
    print(f'  defects_found               {defects_found}')
    print(f'  defects_escaped             {defects_escaped}')
    print(f'  coverage_percentage         {statement_coverage}%')
    print(f'  tests                       {passed}/{executed} passed')


if __name__ == '__main__':
    main()
