import sqlite3
from flask import g


def get_db():
    from app import get_db as _get_db
    return _get_db()


class Employee:
    def __init__(self, id, employee_id, name, email, password_hash,
                 department, hire_date, role):
        self.id = id
        self.employee_id = employee_id
        self.name = name
        self.email = email
        self.password_hash = password_hash
        self.department = department
        self.hire_date = hire_date
        self.role = role

    @staticmethod
    def from_row(row):
        if row is None:
            return None
        return Employee(
            id=row['id'], employee_id=row['employee_id'],
            name=row['name'], email=row['email'],
            password_hash=row['password_hash'],
            department=row['department'], hire_date=row['hire_date'],
            role=row['role']
        )

    @staticmethod
    def get_by_id(user_id):
        db = get_db()
        row = db.execute('SELECT * FROM employee WHERE id = ?', (user_id,)).fetchone()
        return Employee.from_row(row)

    @staticmethod
    def get_by_email(email):
        db = get_db()
        row = db.execute('SELECT * FROM employee WHERE email = ?', (email,)).fetchone()
        return Employee.from_row(row)

    @staticmethod
    def create(employee_id, name, email, password_hash, department, hire_date, role='employee'):
        db = get_db()
        db.execute(
            'INSERT INTO employee (employee_id, name, email, password_hash, department, hire_date, role) '
            'VALUES (?, ?, ?, ?, ?, ?, ?)',
            (employee_id, name, email, password_hash, department, hire_date, role)
        )
        db.commit()
        return Employee.get_by_email(email)


class LeaveRequest:
    VALID_STATUSES = ['Requested', 'Approved', 'Rejected', 'Cancelled', 'Taken']
    VALID_LEAVE_TYPES = ['Annual', 'Sick', 'Personal']

    # Defines which status transitions are allowed
    VALID_TRANSITIONS = {
        'Requested': ['Approved', 'Rejected', 'Cancelled'],
        'Approved': ['Cancelled', 'Taken'],
        'Rejected': [],
        'Cancelled': [],
        'Taken': [],
    }

    def __init__(self, id, employee_id, leave_type, start_date, end_date,
                 days_requested, reason, has_document, status, created_at,
                 reviewed_by, reviewed_at):
        self.id = id
        self.employee_id = employee_id
        self.leave_type = leave_type
        self.start_date = start_date
        self.end_date = end_date
        self.days_requested = days_requested
        self.reason = reason
        self.has_document = has_document
        self.status = status
        self.created_at = created_at
        self.reviewed_by = reviewed_by
        self.reviewed_at = reviewed_at

    @staticmethod
    def from_row(row):
        if row is None:
            return None
        return LeaveRequest(
            id=row['id'], employee_id=row['employee_id'],
            leave_type=row['leave_type'], start_date=row['start_date'],
            end_date=row['end_date'], days_requested=row['days_requested'],
            reason=row['reason'], has_document=bool(row['has_document']),
            status=row['status'], created_at=row['created_at'],
            reviewed_by=row['reviewed_by'], reviewed_at=row['reviewed_at']
        )

    @staticmethod
    def create(employee_id, leave_type, start_date, end_date, days_requested,
               reason='', has_document=False):
        db = get_db()
        cursor = db.execute(
            'INSERT INTO leave_request (employee_id, leave_type, start_date, end_date, '
            'days_requested, reason, has_document) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (employee_id, leave_type, start_date, end_date, days_requested,
             reason, int(has_document))
        )
        db.commit()
        return LeaveRequest.get_by_id(cursor.lastrowid)

    @staticmethod
    def get_by_id(request_id):
        db = get_db()
        row = db.execute('SELECT * FROM leave_request WHERE id = ?', (request_id,)).fetchone()
        return LeaveRequest.from_row(row)

    @staticmethod
    def get_by_employee(employee_id):
        db = get_db()
        rows = db.execute(
            'SELECT * FROM leave_request WHERE employee_id = ? ORDER BY created_at DESC',
            (employee_id,)
        ).fetchall()
        return [LeaveRequest.from_row(r) for r in rows]

    @staticmethod
    def get_pending():
        db = get_db()
        rows = db.execute(
            "SELECT lr.*, e.name as employee_name FROM leave_request lr "
            "JOIN employee e ON lr.employee_id = e.id "
            "WHERE lr.status = 'Requested' ORDER BY lr.created_at ASC"
        ).fetchall()
        return rows

    def can_transition_to(self, new_status):
        return new_status in self.VALID_TRANSITIONS.get(self.status, [])

    def update_status(self, new_status, reviewer_id=None):
        if not self.can_transition_to(new_status):
            return False, f"Cannot transition from {self.status} to {new_status}"
        db = get_db()
        db.execute(
            "UPDATE leave_request SET status = ?, reviewed_by = ?, "
            "reviewed_at = datetime('now') WHERE id = ?",
            (new_status, reviewer_id, self.id)
        )
        db.commit()
        self.status = new_status
        return True, "Status updated"


class LeaveBalance:
    def __init__(self, id, employee_id, leave_type, total_days, used_days):
        self.id = id
        self.employee_id = employee_id
        self.leave_type = leave_type
        self.total_days = total_days
        self.used_days = used_days

    @property
    def remaining_days(self):
        return self.total_days - self.used_days

    @staticmethod
    def from_row(row):
        if row is None:
            return None
        return LeaveBalance(
            id=row['id'], employee_id=row['employee_id'],
            leave_type=row['leave_type'], total_days=row['total_days'],
            used_days=row['used_days']
        )

    @staticmethod
    def get_balance(employee_id, leave_type):
        db = get_db()
        row = db.execute(
            'SELECT * FROM leave_balance WHERE employee_id = ? AND leave_type = ?',
            (employee_id, leave_type)
        ).fetchone()
        return LeaveBalance.from_row(row)

    @staticmethod
    def get_all_balances(employee_id):
        db = get_db()
        rows = db.execute(
            'SELECT * FROM leave_balance WHERE employee_id = ?', (employee_id,)
        ).fetchall()
        return [LeaveBalance.from_row(r) for r in rows]

    @staticmethod
    def create(employee_id, leave_type, total_days):
        db = get_db()
        db.execute(
            'INSERT INTO leave_balance (employee_id, leave_type, total_days, used_days) '
            'VALUES (?, ?, ?, 0)',
            (employee_id, leave_type, total_days)
        )
        db.commit()
        return LeaveBalance.get_balance(employee_id, leave_type)

    @staticmethod
    def deduct(employee_id, leave_type, days):
        db = get_db()
        db.execute(
            'UPDATE leave_balance SET used_days = used_days + ? '
            'WHERE employee_id = ? AND leave_type = ?',
            (days, employee_id, leave_type)
        )
        db.commit()

    @staticmethod
    def restore(employee_id, leave_type, days):
        db = get_db()
        db.execute(
            'UPDATE leave_balance SET used_days = used_days - ? '
            'WHERE employee_id = ? AND leave_type = ?',
            (days, employee_id, leave_type)
        )
        db.commit()
