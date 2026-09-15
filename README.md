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
│   ├── test_routes.py        # Route unit tests
│   ├── test_decision_table.py # Decision table rules R1-R9
│   └── test_state_transitions.py # All 25 ordered state pairs
├── docs/
│   ├── test_plan.md
│   ├── test_design.md
│   ├── test_summary_report.md
│   ├── foundations_reflection.md
│   └── docx/                 # Word copies of the four documents
├── tools/
│   ├── collect_metrics.py    # Regenerates metrics.json from real measurements
│   └── md_to_docx.py         # Regenerates the Word copies
├── defect_log.csv            # Defect log
├── metrics.json              # Quality metrics
├── pytest.ini                # Marker registration
├── requirements.txt
├── run.py                    # Application entry point
└── README.md
```

## Test Documentation

| Document | Markdown | Word |
|---|---|---|
| Test Plan — scope, approach, entry/exit criteria, risk prioritisation, roles | [`docs/test_plan.md`](docs/test_plan.md) | `docs/docx/test_plan.docx` |
| Test Design — equivalence partitioning, boundary value analysis, decision table, state transitions | [`docs/test_design.md`](docs/test_design.md) | `docs/docx/test_design.docx` |
| Test Summary Report — results, exit criteria, outstanding defects, release recommendation | [`docs/test_summary_report.md`](docs/test_summary_report.md) | `docs/docx/test_summary_report.docx` |
| Foundations Reflection — error → fault → failure analysis of DEF-001 | [`docs/foundations_reflection.md`](docs/foundations_reflection.md) | `docs/docx/foundations_reflection.docx` |
| Defect Log | [`defect_log.csv`](defect_log.csv) | — |
| Quality Metrics | [`metrics.json`](metrics.json) | — |

Regenerate the Word copies with `python3 tools/md_to_docx.py` (needs `python-docx`),
and the metrics with `python3 tools/collect_metrics.py`.

## Test Design Techniques

| Technique | Coverage | Automated in |
|---|---|---|
| Equivalence partitioning | 22 partitions, 26 cases | `tests/test_business_logic.py`, `tests/test_decision_table.py` |
| Boundary value analysis | 7 boundaries, 27 cases | `tests/test_business_logic.py`, `tests/test_decision_table.py` |
| Decision table | 9 rules over 5 conditions, 22 cases | `tests/test_decision_table.py` |
| State transition | all 25 ordered state pairs (5 valid, 20 invalid), 41 cases | `tests/test_state_transitions.py` |

## Known Defects

Five defects are open against the current build; see [`defect_log.csv`](defect_log.csv)
for full reproduction steps. Two are Critical and block release:

| ID | Severity | Summary |
|---|---|---|
| DEF-001 | Critical | Cancelling a leave request still in `Requested` restores days that were never deducted, driving `used_days` negative. |
| DEF-002 | Critical | Approval never re-checks the balance, so several pending requests can each be approved past the entitlement. |
| DEF-004 | Medium | `calculate_service_months` undercounts by a month for hire dates on the 29th–31st. |
| DEF-005 | Medium | The `Taken` state is declared but unreachable — no code path ever enters it. |
| DEF-003 | Low | A boolean is accepted as `days_requested` and treated as a one-day request. |

Each defect has a test that reproduces it and asserts the **specified** behaviour, so it
turns into a passing regression test as soon as the defect is fixed. Those tests carry the
`defect` marker and therefore fail by design:

```bash
pytest                    # 152 tests: 147 pass, 5 defect reproducers fail
pytest -m "not defect"    # 147 pass, 5 deselected - the green CI run
pytest -m defect          # just the five reproducers
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

Achieved: **100%** statement and branch coverage on `business_logic.py`, **98.37%** statement
and **94.87%** branch coverage across `app/`. See [`metrics.json`](metrics.json).
