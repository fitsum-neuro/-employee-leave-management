import calendar
from datetime import datetime, date


def calculate_service_months(hire_date_str):
    """Calculate months of service from hire date to today."""
    if isinstance(hire_date_str, str):
        hire_date = datetime.strptime(hire_date_str, '%Y-%m-%d').date()
    else:
        hire_date = hire_date_str

    today = date.today()
    months = (today.year - hire_date.year) * 12 + (today.month - hire_date.month)

    # Account for short months: if hire day exceeds the last day of the
    # current month, the anniversary falls on the last day of that month.
    last_day_of_month = calendar.monthrange(today.year, today.month)[1]
    anniversary_day = min(hire_date.day, last_day_of_month)
    if today.day < anniversary_day:
        months -= 1

    return max(months, 0)


def calculate_leave_balance(employee_id, leave_type, get_balance_func=None):
    """Return remaining leave days for an employee and leave type."""
    if get_balance_func:
        balance = get_balance_func(employee_id, leave_type)
    else:
        from app.models import LeaveBalance
        balance = LeaveBalance.get_balance(employee_id, leave_type)

    if balance is None:
        return 0
    return balance.remaining_days


def check_eligibility(employee, leave_type, days_requested, has_document,
                      get_balance_func=None):
    """
    Check if an employee is eligible to take leave.

    Rules:
    - Employee must have >= 6 months of service
    - days_requested must be between 1 and 30 (inclusive)
    - leave_type must be one of: Annual, Sick, Personal
    - Employee must have sufficient balance
    - Sick leave > 3 days requires a supporting document

    Returns (eligible: bool, reason: str)
    """
    valid_types = ['Annual', 'Sick', 'Personal']
    if leave_type not in valid_types:
        return False, f"Invalid leave type. Must be one of: {', '.join(valid_types)}"

    # Reject booleans explicitly — bool is a subclass of int in Python
    if isinstance(days_requested, bool) or not isinstance(days_requested, int):
        return False, "Days requested must be at least 1"

    if days_requested < 0:  # BUG: should be < 1; allows 0-day requests through
        return False, "Days requested must be at least 1"

    if days_requested > 30:
        return False, "Days requested cannot exceed 30"

    service_months = calculate_service_months(employee.hire_date)
    if service_months < 6:
        return False, f"Minimum 6 months of service required. Current: {service_months} months"

    remaining = calculate_leave_balance(employee.id, leave_type, get_balance_func)
    if days_requested > remaining:
        return False, f"Insufficient balance. Available: {remaining} days"

    if leave_type == 'Sick' and days_requested > 3 and not has_document:
        return False, "Supporting document required for sick leave exceeding 3 days"

    return True, "Eligible"


def validate_leave_dates(start_date_str, end_date_str):
    """
    Validate leave request dates.
    Returns (valid: bool, reason: str, days: int)
    """
    try:
        start = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return False, "Invalid date format. Use YYYY-MM-DD", 0

    if start < date.today():
        return False, "Start date cannot be in the past", 0

    if end < start:
        return False, "End date must be on or after start date", 0

    days = (end - start).days + 1
    return True, "Valid dates", days


def process_leave_request(employee, leave_type, start_date, end_date,
                          has_document=False, reason='',
                          get_balance_func=None, create_request_func=None):
    """
    Full orchestrator: validate dates, check eligibility, create request.
    Returns (success: bool, message: str, request_obj or None)
    """
    valid, msg, days = validate_leave_dates(start_date, end_date)
    if not valid:
        return False, msg, None

    eligible, reason_msg = check_eligibility(
        employee, leave_type, days, has_document, get_balance_func
    )
    if not eligible:
        return False, reason_msg, None

    if create_request_func:
        leave_req = create_request_func(
            employee.id, leave_type, start_date, end_date, days, reason, has_document
        )
    else:
        from app.models import LeaveRequest
        leave_req = LeaveRequest.create(
            employee.id, leave_type, start_date, end_date, days, reason, has_document
        )

    return True, "Leave request submitted successfully", leave_req
