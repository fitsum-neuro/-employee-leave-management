# Employee Leave Management System

A web-based employee leave management system built with Python/Flask for the Software Testing & Validation course final project.

## Team Members

| Name | Student ID | Role |
|------|-----------|------|
| Fitsum Yoseph | ATE/5804/16 | Person 1 — Application Developer |
| Henok Zemedkun | ATE/8552/16 | Person 2 — Test Architect & Document Author |
| Eyob Kassaye | ATE/4534/16 | Person 3 — Test Automation Engineer & CI/CD |

## Features

- Employee login/logout with session management
- Leave request submission (Annual, Sick, Personal)
- Leave balance tracking per leave type
- Leave history with cancel functionality
- Admin panel for approving/rejecting requests
- State transition management (Requested → Approved/Rejected/Cancelled → Taken)
- Business rules: 6-month service requirement, 1-30 day range, sick leave document requirement

## Tech Stack

- **Backend:** Python 3, Flask
- **Database:** SQLite
- **Testing:** pytest, pytest-cov, unittest.mock
- **CI/CD:** GitHub Actions, Jenkins (Docker)
- **System Tests:** Selenium with Page Object pattern

## Setup & Installation

```bash
# Clone the repository
git clone <repo-url>
cd employee-leave-management

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Running the Application

```bash
python run.py
```

The app starts at `http://localhost:5000`. On first run, it seeds:
- **Admin:** admin@company.com / admin123
- **Employee:** john@company.com / password123

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=app --cov-report=html --cov-report=term-missing

# Run only unit tests
pytest tests/test_business_logic.py tests/test_routes.py

# Run with branch coverage on core business logic
pytest --cov=app/business_logic --cov-branch --cov-report=term-missing
```

## Project Structure

```
employee-leave-management/
├── app/
│   ├── __init__.py           # Flask app factory + DB schema
│   ├── models.py             # Employee, LeaveRequest, LeaveBalance models
│   ├── business_logic.py     # Eligibility checks, balance calculations
│   ├── auth.py               # Authentication and decorators
│   ├── routes.py             # All Flask routes
│   ├── templates/            # Jinja2 HTML templates
│   └── static/style.css      # Stylesheet
├── tests/
│   ├── conftest.py           # Shared fixtures
│   ├── test_business_logic.py # Unit tests + test doubles (mock, fake, spy)
│   └── test_routes.py        # Route unit tests
├── requirements.txt
├── run.py                    # Application entry point
└── README.md
```

## Test Doubles Used

| Type | Where | Purpose |
|------|-------|---------|
| **Fake** | `FakeBalanceStore` in test_business_logic.py | In-memory balance store replacing the DB |
| **Mock** | `MagicMock` for create_request_func | Replaces DB write in process_leave_request |
| **Spy** | `MagicMock(wraps=...)` on get_balance | Tracks calls while preserving behavior |

## CI Pipelines

### GitHub Actions
The `.github/workflows/test.yml` pipeline runs on every push: installs dependencies, runs all tests, and reports coverage.

### Jenkins
The `Jenkinsfile` defines stages: Setup → Unit Tests → Integration Tests → System Tests. See Jenkins Docker setup instructions in the project docs.

## Business Rules

| Rule | Description |
|------|-------------|
| Service requirement | Employee must have ≥ 6 months of service |
| Day range | Leave requests must be 1–30 days |
| Leave types | Annual, Sick, Personal |
| Sick leave document | Sick leave > 3 days requires supporting document |
| State transitions | Requested → Approved/Rejected/Cancelled; Approved → Taken/Cancelled |

## Coverage Target

Minimum **80% branch coverage** on `business_logic.py`. Coverage reports are generated in `htmlcov/`.
