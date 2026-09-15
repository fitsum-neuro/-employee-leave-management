"""
Decision table tests for the leave eligibility rule set.

Automates every rule R1-R9 of the decision table in docs/test_design.md section 4,
plus the precedence cases that prove the rules fire in the order the specification
requires. Case IDs (DT-nn) match the Test Design Document.

Author: Henok Zemedkun (ATE/8552/16) - Person 2, Test Architect

Conditions
    C1 leave_type is Annual / Sick / Personal
    C2 1 <= days_requested <= 30 and days_requested is an integer
    C3 service_months >= 6
    C4 days_requested <= remaining balance
    C5 a document is required (leave_type == 'Sick' and days_requested > 3)
    C6 has_document

Actions
    A1 accept          A2 invalid type     A3 days below minimum   A4 days above maximum
    A5 insufficient service                A6 insufficient balance A7 document required

Tests marked `defect` reproduce a logged defect and are expected to fail against the
current build. Run `pytest -m "not defect"` to exclude them.
"""
import calendar
from datetime import date, timedelta
from unittest.mock import patch

import pytest

from app.business_logic import (
    calculate_service_months,
    check_eligibility,
    process_leave_request,
)
from app.models import Employee, LeaveBalance


# --------------------------------------------------------------------------
# Helpers: lightweight stand-ins so a rule can be driven to an exact
# service length or balance without reshaping the database each time.
# check_eligibility only reads `.id` and `.hire_date` off the employee.
# --------------------------------------------------------------------------

class EmployeeStub:
    """Minimal employee double for unit-level decision table rules."""

    def __init__(self, id=1, hire_date='2020-01-01'):
        self.id = id
        self.hire_date = hire_date


class BalanceStub:
    """Minimal leave balance double exposing only `remaining_days`."""

    def __init__(self, remaining):
        self.remaining_days = remaining


def balance_of(remaining):
    """A get_balance_func that always reports `remaining` days left."""
    return lambda employee_id, leave_type: BalanceStub(remaining)


def no_balance_record():
    """A get_balance_func standing in for an employee with no balance row."""
    return lambda employee_id, leave_type: None


def hired_months_ago(n):
    """
    An ISO hire date exactly `n` whole months before today.

    The day of month is clamped to the length of the target month so the returned
    date always yields exactly `n` from calculate_service_months, whatever today is.
    """
    today = date.today()
    year, month = today.year, today.month - n
    while month <= 0:
        month += 12
        year -= 1
    day = min(today.day, calendar.monthrange(year, month)[1])
    return date(year, month, day).strftime('%Y-%m-%d')


def days_from_now(n):
    return (date.today() + timedelta(days=n)).strftime('%Y-%m-%d')


ELIGIBLE = EmployeeStub(id=1, hire_date='2020-01-01')


# ==========================================================================
# R1  C1=N  ->  A2 invalid leave type
# ==========================================================================

class TestRule1InvalidLeaveType:

    def test_dt_01_unrecognised_leave_type_is_refused(self):
        """DT-01: an invalid leave type is refused before any other condition."""
        eligible, reason = check_eligibility(
            ELIGIBLE, 'Maternity', 5, False, balance_of(20)
        )
        assert eligible is False
        assert reason == (
            'Invalid leave type. Must be one of: Annual, Sick, Personal'
        )

    @pytest.mark.parametrize('leave_type', ['annual', 'SICK', 'Holiday', '', None])
    def test_dt_01_variants_of_invalid_type(self, leave_type):
        """DT-01: matching is case sensitive and rejects empty and None types."""
        eligible, reason = check_eligibility(
            ELIGIBLE, leave_type, 5, False, balance_of(20)
        )
        assert eligible is False
        assert 'Invalid leave type' in reason

    def test_dt_02_invalid_type_takes_precedence_over_every_other_failure(self):
        """
        DT-02: rule precedence. Type, days, service and balance all fail at once;
        R1 must win, so the message names the leave type and nothing else.
        """
        ineligible = EmployeeStub(id=2, hire_date=hired_months_ago(1))
        eligible, reason = check_eligibility(
            ineligible, 'Maternity', 99, False, no_balance_record()
        )
        assert eligible is False
        assert 'Invalid leave type' in reason
        assert 'service' not in reason
        assert 'balance' not in reason


# ==========================================================================
# R2  C1=Y, days < 1  ->  A3 days below minimum
# ==========================================================================

class TestRule2DaysBelowMinimum:

    @pytest.mark.parametrize('days', [0, -1, -5])
    def test_dt_03_day_count_below_minimum_is_refused(self, days):
        """DT-03: zero and negative day counts are refused."""
        eligible, reason = check_eligibility(
            ELIGIBLE, 'Annual', days, False, balance_of(20)
        )
        assert eligible is False
        assert reason == 'Days requested must be at least 1'

    @pytest.mark.parametrize('days', ['5', 5.5, None])
    def test_dt_03_non_integer_day_count_is_refused(self, days):
        """DT-03: a non-integer day count is refused rather than raising."""
        eligible, reason = check_eligibility(
            ELIGIBLE, 'Annual', days, False, balance_of(20)
        )
        assert eligible is False
        assert reason == 'Days requested must be at least 1'

    def test_dt_04_day_range_takes_precedence_over_service(self):
        """DT-04: R2 fires before R4 when both the day count and service fail."""
        ineligible = EmployeeStub(id=2, hire_date=hired_months_ago(1))
        eligible, reason = check_eligibility(
            ineligible, 'Annual', 0, False, balance_of(20)
        )
        assert eligible is False
        assert reason == 'Days requested must be at least 1'


# ==========================================================================
# R3  C1=Y, days > 30  ->  A4 days above maximum
# ==========================================================================

class TestRule3DaysAboveMaximum:

    @pytest.mark.parametrize('days', [31, 45, 365])
    def test_dt_05_day_count_above_maximum_is_refused(self, days):
        """DT-05: any request over 30 days is refused on the range rule."""
        eligible, reason = check_eligibility(
            ELIGIBLE, 'Annual', days, False, balance_of(400)
        )
        assert eligible is False
        assert reason == 'Days requested cannot exceed 30'

    def test_dt_06_day_range_takes_precedence_over_balance(self):
        """
        DT-06: 35 days breaches both the range and a 20-day balance.
        R3 is checked first, so the message must be the range one.
        """
        eligible, reason = check_eligibility(
            ELIGIBLE, 'Annual', 35, False, balance_of(20)
        )
        assert eligible is False
        assert reason == 'Days requested cannot exceed 30'
        assert 'balance' not in reason


# ==========================================================================
# R4  C1=Y, C2=Y, service < 6  ->  A5 insufficient service
# ==========================================================================

class TestRule4InsufficientService:

    @pytest.mark.parametrize('months', [0, 1, 2, 5])
    def test_dt_07_service_under_six_months_is_refused(self, months):
        """DT-07: an employee below the six-month threshold is refused."""
        employee = EmployeeStub(id=3, hire_date=hired_months_ago(months))
        eligible, reason = check_eligibility(
            employee, 'Annual', 5, False, balance_of(20)
        )
        assert eligible is False
        assert reason == (
            f'Minimum 6 months of service required. Current: {months} months'
        )

    def test_dt_08_service_takes_precedence_over_balance(self):
        """DT-08: R4 fires before R5 when both service and balance fail."""
        employee = EmployeeStub(id=3, hire_date=hired_months_ago(2))
        eligible, reason = check_eligibility(
            employee, 'Annual', 5, False, balance_of(1)
        )
        assert eligible is False
        assert 'Minimum 6 months of service required' in reason
        assert 'balance' not in reason


# ==========================================================================
# R5  C1=Y, C2=Y, C3=Y, balance insufficient  ->  A6 insufficient balance
# ==========================================================================

class TestRule5InsufficientBalance:

    def test_dt_09_request_over_remaining_balance_is_refused(self):
        """DT-09: 25 days against a 20-day balance is refused."""
        eligible, reason = check_eligibility(
            ELIGIBLE, 'Annual', 25, False, balance_of(20)
        )
        assert eligible is False
        assert reason == 'Insufficient balance. Available: 20 days'

    def test_dt_09_missing_balance_record_counts_as_zero(self):
        """DT-09: no balance row is treated as zero remaining, not as an error."""
        eligible, reason = check_eligibility(
            ELIGIBLE, 'Personal', 1, False, no_balance_record()
        )
        assert eligible is False
        assert reason == 'Insufficient balance. Available: 0 days'

    def test_dt_10_balance_takes_precedence_over_document_rule(self):
        """
        DT-10: 10 days of sick leave with no document breaches both R5 and R6.
        Balance is checked first, so A6 must be the action.
        """
        eligible, reason = check_eligibility(
            ELIGIBLE, 'Sick', 10, False, balance_of(5)
        )
        assert eligible is False
        assert reason == 'Insufficient balance. Available: 5 days'
        assert 'document' not in reason

    def test_dt_21_rule_uses_remaining_not_total_days(self, app, sample_employee):
        """DT-21: R5 is evaluated against remaining days, not the entitlement."""
        with app.app_context():
            LeaveBalance.create(sample_employee.id, 'Annual', 20)
            LeaveBalance.deduct(sample_employee.id, 'Annual', 15)
            eligible, reason = check_eligibility(
                sample_employee, 'Annual', 10, False
            )
        assert eligible is False
        assert reason == 'Insufficient balance. Available: 5 days'


# ==========================================================================
# R6  C5=Y, C6=N  ->  A7 supporting document required
# ==========================================================================

class TestRule6DocumentRequired:

    @pytest.mark.parametrize('days', [4, 7, 15])
    def test_dt_11_long_sick_leave_without_document_is_refused(self, days):
        """DT-11: sick leave over three days demands a supporting document."""
        eligible, reason = check_eligibility(
            ELIGIBLE, 'Sick', days, False, balance_of(30)
        )
        assert eligible is False
        assert reason == (
            'Supporting document required for sick leave exceeding 3 days'
        )


# ==========================================================================
# R7  C5=Y, C6=Y  ->  A1 accept
# ==========================================================================

class TestRule7LongSickLeaveWithDocument:

    @pytest.mark.parametrize('days', [4, 10, 30])
    def test_dt_12_long_sick_leave_with_document_is_accepted(self, days):
        """DT-12: the same request with a document supplied is accepted."""
        eligible, reason = check_eligibility(
            ELIGIBLE, 'Sick', days, True, balance_of(30)
        )
        assert eligible is True
        assert reason == 'Eligible'


# ==========================================================================
# R8  C5=N, C6=N  ->  A1 accept
# ==========================================================================

class TestRule8NoDocumentNeededNoneSupplied:

    def test_dt_13_annual_leave_is_accepted(self):
        """DT-13: annual leave never triggers the document rule."""
        eligible, reason = check_eligibility(
            ELIGIBLE, 'Annual', 10, False, balance_of(20)
        )
        assert eligible is True
        assert reason == 'Eligible'

    @pytest.mark.parametrize('days', [1, 2, 3])
    def test_dt_14_short_sick_leave_is_accepted_without_document(self, days):
        """DT-14: the document rule applies only *above* three days."""
        eligible, reason = check_eligibility(
            ELIGIBLE, 'Sick', days, False, balance_of(15)
        )
        assert eligible is True
        assert reason == 'Eligible'

    def test_dt_15_personal_leave_is_accepted(self):
        """DT-15: personal leave for the whole remaining balance is accepted."""
        eligible, reason = check_eligibility(
            ELIGIBLE, 'Personal', 5, False, balance_of(5)
        )
        assert eligible is True
        assert reason == 'Eligible'


# ==========================================================================
# R9  C5=N, C6=Y  ->  A1 accept  (the document is ignored, not penalised)
# ==========================================================================

class TestRule9DocumentSuppliedButNotNeeded:

    def test_dt_16_document_on_annual_leave_is_ignored(self):
        """DT-16: supplying a document where none is required is harmless."""
        eligible, reason = check_eligibility(
            ELIGIBLE, 'Annual', 10, True, balance_of(20)
        )
        assert eligible is True
        assert reason == 'Eligible'

    def test_dt_17_document_on_short_sick_leave_is_ignored(self):
        """DT-17: short sick leave with a document is accepted."""
        eligible, reason = check_eligibility(
            ELIGIBLE, 'Sick', 3, True, balance_of(15)
        )
        assert eligible is True
        assert reason == 'Eligible'

    @pytest.mark.parametrize(
        'leave_type,days', [('Annual', 10), ('Personal', 5), ('Sick', 3)]
    )
    def test_dt_18_document_flag_is_irrelevant_when_c5_is_false(
        self, leave_type, days
    ):
        """
        DT-18: R8 and R9 must produce identical results. This is the case that
        would catch a fault where has_document is consulted unconditionally.
        """
        without = check_eligibility(
            ELIGIBLE, leave_type, days, False, balance_of(20)
        )
        with_doc = check_eligibility(
            ELIGIBLE, leave_type, days, True, balance_of(20)
        )
        assert without == with_doc == (True, 'Eligible')


# ==========================================================================
# Defect probes - expected to fail against the current build
# ==========================================================================

class TestDecisionTableDefectProbes:

    @pytest.mark.defect
    def test_dt_19_boolean_day_count_is_a_wrong_type_not_one_day(self):
        """
        DT-19 (DEF-003, rule R2 extension).

        bool is a subclass of int in Python, so `isinstance(True, int)` is True
        and `True >= 1` holds. A boolean therefore slips past the type guard in
        business_logic.py:49 and is processed as a one-day request instead of
        being refused as an invalid day count.
        """
        eligible, reason = check_eligibility(
            ELIGIBLE, 'Annual', True, False, balance_of(20)
        )
        assert eligible is False, (
            'DEF-003: days_requested=True was accepted as a 1-day request'
        )
        assert reason == 'Days requested must be at least 1'

    @pytest.mark.defect
    def test_dt_20_service_months_at_a_month_end_hire_date(self):
        """
        DT-20 (DEF-004, rule R4 extension).

        An employee hired on 2024-08-31 completes six months on 2025-02-28,
        the last day of February, because February has no 31st. The guard
        `if today.day < hire_date.day` in business_logic.py:13 does not account
        for short months, so it subtracts a month that has in fact elapsed and
        the employee is refused leave for which they are eligible.
        """

        class FrozenDate(date):
            @classmethod
            def today(cls):
                return date(2025, 2, 28)

        with patch('app.business_logic.date', FrozenDate):
            months = calculate_service_months('2024-08-31')
            employee = EmployeeStub(id=4, hire_date='2024-08-31')
            eligible, reason = check_eligibility(
                employee, 'Annual', 5, False, balance_of(20)
            )

        assert months == 6, (
            f'DEF-004: expected 6 months of service on 2025-02-28 for a '
            f'2024-08-31 hire date, got {months}'
        )
        assert eligible is True, f'DEF-004: employee wrongly refused - {reason}'


# ==========================================================================
# DT-22  every rule holds end to end through process_leave_request
# ==========================================================================

class TestDecisionTableEndToEnd:
    """
    DT-22: each rule is re-checked through the full orchestrator so that a rule
    proven at unit level cannot be lost in the layer above. A request object is
    created only for the accepting rules R7-R9.
    """

    @pytest.mark.parametrize(
        'rule,leave_type,span,has_document,remaining,expected_fragment',
        [
            ('R1', 'Maternity', 4, False, 20, 'Invalid leave type'),
            ('R3', 'Annual', 34, False, 40, 'cannot exceed 30'),
            ('R5', 'Annual', 24, False, 10, 'Insufficient balance'),
            ('R6', 'Sick', 9, False, 20, 'Supporting document required'),
        ],
    )
    def test_dt_22_rejecting_rules_create_no_request(
        self, rule, leave_type, span, has_document, remaining, expected_fragment
    ):
        created = []

        def spy_create(*args, **kwargs):
            created.append(args)
            return object()

        success, message, leave_req = process_leave_request(
            ELIGIBLE, leave_type,
            days_from_now(5), days_from_now(5 + span),
            has_document=has_document, reason='decision table',
            get_balance_func=balance_of(remaining),
            create_request_func=spy_create,
        )

        assert success is False, f'{rule} should have been refused'
        assert expected_fragment in message
        assert leave_req is None
        assert created == [], f'{rule} must not create a leave request'

    def test_dt_22_r4_insufficient_service_creates_no_request(self):
        employee = EmployeeStub(id=5, hire_date=hired_months_ago(3))
        created = []
        success, message, leave_req = process_leave_request(
            employee, 'Annual', days_from_now(5), days_from_now(9),
            get_balance_func=balance_of(20),
            create_request_func=lambda *a: created.append(a),
        )
        assert success is False
        assert 'Minimum 6 months of service required' in message
        assert leave_req is None
        assert created == []

    @pytest.mark.parametrize(
        'rule,leave_type,span,has_document',
        [
            ('R7', 'Sick', 9, True),
            ('R8', 'Annual', 9, False),
            ('R9', 'Annual', 9, True),
        ],
    )
    def test_dt_22_accepting_rules_create_the_request(
        self, rule, leave_type, span, has_document
    ):
        created = []

        def spy_create(*args, **kwargs):
            created.append(args)
            return {'id': 1}

        success, message, leave_req = process_leave_request(
            ELIGIBLE, leave_type,
            days_from_now(5), days_from_now(5 + span),
            has_document=has_document, reason='decision table',
            get_balance_func=balance_of(20),
            create_request_func=spy_create,
        )

        assert success is True, f'{rule} should have been accepted: {message}'
        assert message == 'Leave request submitted successfully'
        assert leave_req is not None
        assert len(created) == 1
        assert created[0][4] == span + 1, 'the inclusive day count must be passed on'

    def test_dt_22_accepting_rule_through_the_real_database(
        self, app, sample_employee, sample_balance
    ):
        """DT-22: rule R8 end to end against the real model layer and SQLite."""
        with app.app_context():
            success, message, leave_req = process_leave_request(
                sample_employee, 'Annual',
                days_from_now(10), days_from_now(14),
                has_document=False, reason='annual break',
            )
            assert success is True, message
            assert leave_req is not None
            assert leave_req.days_requested == 5
            assert leave_req.status == 'Requested'
            assert leave_req.leave_type == 'Annual'
