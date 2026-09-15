from app import create_app
from app.auth import hash_password
from app.models import Employee, LeaveBalance

app = create_app()


def seed_data():
    """Create default admin and sample employee if the database is empty."""
    with app.app_context():
        from app import get_db
        db = get_db()
        existing = db.execute('SELECT COUNT(*) FROM employee').fetchone()[0]
        if existing > 0:
            return

        # Admin user
        Employee.create(
            employee_id='ADM001', name='Admin User',
            email='admin@company.com',
            password_hash=hash_password('admin123'),
            department='Management',
            hire_date='2020-01-15', role='admin'
        )
        # Regular employee (hired > 6 months ago)
        emp = Employee.create(
            employee_id='EMP001', name='John Doe',
            email='john@company.com',
            password_hash=hash_password('password123'),
            department='Engineering',
            hire_date='2025-01-10', role='employee'
        )
        # Set up leave balances for the employee
        for leave_type, total in [('Annual', 20), ('Sick', 15), ('Personal', 5)]:
            LeaveBalance.create(emp.id, leave_type, total)


if __name__ == '__main__':
    seed_data()
    app.run(debug=True, port=5000)
