import os
import tempfile
import pytest
from app import create_app, get_db
from app.auth import hash_password
from app.models import Employee, LeaveBalance, LeaveRequest


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp()
    test_app = create_app({
        'TESTING': True,
        'DATABASE': db_path,
        'SECRET_KEY': 'test-secret',
    })

    yield test_app

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


@pytest.fixture
def sample_employee(app):
    with app.app_context():
        emp = Employee.create(
            employee_id='EMP001', name='Test Employee',
            email='test@company.com',
            password_hash=hash_password('password123'),
            department='Engineering',
            hire_date='2025-01-01', role='employee'
        )
        return emp


@pytest.fixture
def sample_admin(app):
    with app.app_context():
        admin = Employee.create(
            employee_id='ADM001', name='Test Admin',
            email='admin@company.com',
            password_hash=hash_password('admin123'),
            department='Management',
            hire_date='2020-01-01', role='admin'
        )
        return admin


@pytest.fixture
def sample_balance(app, sample_employee):
    with app.app_context():
        balances = {}
        for leave_type, total in [('Annual', 20), ('Sick', 15), ('Personal', 5)]:
            b = LeaveBalance.create(sample_employee.id, leave_type, total)
            balances[leave_type] = b
        return balances


@pytest.fixture
def auth_client(client, sample_employee):
    """A test client already logged in as the sample employee."""
    client.post('/login', data={
        'email': 'test@company.com',
        'password': 'password123'
    })
    return client


@pytest.fixture
def admin_client(client, sample_admin):
    """A test client already logged in as the admin."""
    client.post('/login', data={
        'email': 'admin@company.com',
        'password': 'admin123'
    })
    return client
