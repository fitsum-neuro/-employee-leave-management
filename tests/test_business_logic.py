"""
Unit tests for business_logic.py.
Includes test doubles: mock (DB calls), fake (in-memory balance store), spy (calculate_leave_balance).
"""
import pytest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock, call
from app.business_logic import (
    calculate_service_months,
    calculate_leave_balance,
    check_eligibility,
    validate_leave_dates,
    process_leave_request,
)


# --- Helper: simple employee-like object for tests ---
class FakeEmployee:
    def __init__(self, id=1, hire_date='2025-01-01'):
        self.id = id
        self.hire_date = hire_date


# --- Fake in-memory balance store (test double: fake) ---
class FakeBalanceStore:
    """In-memory leave balance store used as a test double."""

    def __init__(self):
        self.store = {}

    def add(self, employee_id, leave_type, total, used=0):
        key = (employee_id, leave_type)
        self.store[key] = MagicMock(remaining_days=total - used)

    def get_balance(self, employee_id, leave_type):
        return self.store.get((employee_id, leave_type))


# ==================== calculate_service_months ====================

class TestCalculateServiceMonths:

    def test_zero_months_for_today(self):
        today = date.today().strftime('%Y-%m-%d')
        assert calculate_service_months(today) == 0

    def test_six_months(self):
        six_months_ago = date.today().replace(
            month=date.today().month - 6 if date.today().month > 6
            else date.today().month + 6,
            year=date.today().year if date.today().month > 6
            else date.today().year - 1
        )
        result = calculate_service_months(six_months_ago.strftime('%Y-%m-%d'))
        assert result == 6

    def test_one_year(self):
        one_year_ago = date.today().replace(year=date.today().year - 1)
        assert calculate_service_months(one_year_ago.strftime('%Y-%m-%d')) == 12

    def test_accepts_date_object(self):
        d = date.today().replace(year=date.today().year - 2)
        assert calculate_service_months(d) == 24


# ==================== calculate_leave_balance ====================

class TestCalculateLeaveBalance:

    def test_with_fake_store(self):
        """Uses fake balance store (test double: fake)."""
        store = FakeBalanceStore()
        store.add(1, 'Annual', total=20, used=5)
        result = calculate_leave_balance(1, 'Annual', get_balance_func=store.get_balance)
        assert result == 15

    def test_no_balance_returns_zero(self):
        store = FakeBalanceStore()
        result = calculate_leave_balance(999, 'Annual', get_balance_func=store.get_balance)
        assert result == 0

    def test_fully_used_balance(self):
        store = FakeBalanceStore()
        store.add(1, 'Sick', total=10, used=10)
        result = calculate_leave_balance(1, 'Sick', get_balance_func=store.get_balance)
        assert result == 0


# ==================== check_eligibility ====================

class TestCheckEligibility:

    @pytest.fixture
    def eligible_employee(self):
        return FakeEmployee(id=1, hire_date='2025-01-01')

    @pytest.fixture
    def new_employee(self):
        return FakeEmployee(id=2, hire_date=date.today().strftime('%Y-%m-%d'))

    @pytest.fixture
    def balance_func(self):
        store = FakeBalanceStore()
        store.add(1, 'Annual', total=20, used=0)
        store.add(1, 'Sick', total=15, used=0)
        store.add(1, 'Personal', total=5, used=0)
        store.add(2, 'Annual', total=20, used=0)
        return store.get_balance

    def test_eligible_annual_leave(self, eligible_employee, balance_func):
        ok, msg = check_eligibility(eligible_employee, 'Annual', 5, False, balance_func)
        assert ok is True
        assert msg == "Eligible"

    def test_invalid_leave_type(self, eligible_employee, balance_func):
        ok, msg = check_eligibility(eligible_employee, 'Vacation', 5, False, balance_func)
        assert ok is False
        assert "Invalid leave type" in msg

    def test_days_less_than_one(self, eligible_employee, balance_func):
        ok, msg = check_eligibility(eligible_employee, 'Annual', 0, False, balance_func)
        assert ok is False
        assert "at least 1" in msg

    def test_days_exceeds_thirty(self, eligible_employee, balance_func):
        ok, msg = check_eligibility(eligible_employee, 'Annual', 31, False, balance_func)
        assert ok is False
        assert "cannot exceed 30" in msg

    def test_insufficient_service_months(self, new_employee, balance_func):
        ok, msg = check_eligibility(new_employee, 'Annual', 5, False, balance_func)
        assert ok is False
        assert "6 months" in msg

    def test_insufficient_balance(self, eligible_employee):
        store = FakeBalanceStore()
        store.add(1, 'Personal', total=5, used=4)
        ok, msg = check_eligibility(eligible_employee, 'Personal', 3, False, store.get_balance)
        assert ok is False
        assert "Insufficient balance" in msg

    def test_sick_leave_over_3_days_no_document(self, eligible_employee, balance_func):
        ok, msg = check_eligibility(eligible_employee, 'Sick', 4, False, balance_func)
        assert ok is False
        assert "document required" in msg.lower()

    def test_sick_leave_over_3_days_with_document(self, eligible_employee, balance_func):
        ok, msg = check_eligibility(eligible_employee, 'Sick', 4, True, balance_func)
        assert ok is True

    def test_sick_leave_3_days_no_document_ok(self, eligible_employee, balance_func):
        ok, msg = check_eligibility(eligible_employee, 'Sick', 3, False, balance_func)
        assert ok is True

    def test_negative_days(self, eligible_employee, balance_func):
        ok, msg = check_eligibility(eligible_employee, 'Annual', -1, False, balance_func)
        assert ok is False

    def test_non_integer_days(self, eligible_employee, balance_func):
        ok, msg = check_eligibility(eligible_employee, 'Annual', 2.5, False, balance_func)
        assert ok is False

    def test_boolean_days_rejected(self, eligible_employee, balance_func):
        ok, msg = check_eligibility(eligible_employee, 'Annual', True, False, balance_func)
        assert ok is False
        assert "at least 1" in msg


# ==================== validate_leave_dates ====================

class TestValidateLeaveDates:

    def test_valid_dates(self):
        start = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
        end = (date.today() + timedelta(days=5)).strftime('%Y-%m-%d')
        valid, msg, days = validate_leave_dates(start, end)
        assert valid is True
        assert days == 5

    def test_same_day(self):
        day = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
        valid, msg, days = validate_leave_dates(day, day)
        assert valid is True
        assert days == 1

    def test_past_start_date(self):
        start = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')
        end = (date.today() + timedelta(days=3)).strftime('%Y-%m-%d')
        valid, msg, _ = validate_leave_dates(start, end)
        assert valid is False
        assert "past" in msg.lower()

    def test_end_before_start(self):
        start = (date.today() + timedelta(days=5)).strftime('%Y-%m-%d')
        end = (date.today() + timedelta(days=2)).strftime('%Y-%m-%d')
        valid, msg, _ = validate_leave_dates(start, end)
        assert valid is False
        assert "after start" in msg.lower()

    def test_invalid_format(self):
        valid, msg, _ = validate_leave_dates('not-a-date', '2025-12-01')
        assert valid is False
        assert "Invalid date" in msg

    def test_none_input(self):
        valid, msg, _ = validate_leave_dates(None, None)
        assert valid is False


# ==================== process_leave_request ====================

class TestProcessLeaveRequest:

    def test_successful_request(self):
        emp = FakeEmployee(id=1, hire_date='2025-01-01')
        store = FakeBalanceStore()
        store.add(1, 'Annual', total=20, used=0)

        start = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
        end = (date.today() + timedelta(days=3)).strftime('%Y-%m-%d')

        created = MagicMock()
        create_func = MagicMock(return_value=created)

        success, msg, req = process_leave_request(
            emp, 'Annual', start, end,
            get_balance_func=store.get_balance,
            create_request_func=create_func,
        )
        assert success is True
        assert "submitted" in msg.lower()
        create_func.assert_called_once()

    def test_invalid_dates_rejected(self):
        emp = FakeEmployee(id=1, hire_date='2025-01-01')
        success, msg, req = process_leave_request(
            emp, 'Annual', '2020-01-01', '2020-01-05'
        )
        assert success is False
        assert req is None

    def test_ineligible_rejected(self):
        emp = FakeEmployee(id=1, hire_date=date.today().strftime('%Y-%m-%d'))
        start = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
        end = (date.today() + timedelta(days=3)).strftime('%Y-%m-%d')

        store = FakeBalanceStore()
        store.add(1, 'Annual', total=20, used=0)

        success, msg, req = process_leave_request(
            emp, 'Annual', start, end,
            get_balance_func=store.get_balance
        )
        assert success is False
        assert req is None


# ==================== Spy test double demo ====================

class TestSpyOnCalculateLeaveBalance:
    """Demonstrates use of a spy test double on calculate_leave_balance."""

    def test_spy_records_call(self):
        store = FakeBalanceStore()
        store.add(1, 'Annual', total=20, used=5)

        spy_func = MagicMock(wraps=store.get_balance)
        result = calculate_leave_balance(1, 'Annual', get_balance_func=spy_func)

        assert result == 15
        spy_func.assert_called_once_with(1, 'Annual')

    def test_spy_tracks_multiple_calls(self):
        store = FakeBalanceStore()
        store.add(1, 'Annual', total=20, used=5)
        store.add(1, 'Sick', total=15, used=3)

        spy_func = MagicMock(wraps=store.get_balance)
        calculate_leave_balance(1, 'Annual', get_balance_func=spy_func)
        calculate_leave_balance(1, 'Sick', get_balance_func=spy_func)

        assert spy_func.call_count == 2
        spy_func.assert_any_call(1, 'Annual')
        spy_func.assert_any_call(1, 'Sick')
