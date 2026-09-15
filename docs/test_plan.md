# Test Plan — Employee Leave Management System

## Document Control

| Field | Value |
|---|---|
| Document | Test Plan |
| Project | Employee Leave Management System |
| Course | Software Testing & Validation — Final Project |
| Version | 1.0 |
| Date | 2026-09-15 |
| Author | Henok Zemedkun (Person 2 — Test Architect & Document Author) |
| Status | Baselined |

### Team Members

| Name | Student ID | Role |
|---|---|---|
| Fitsum Yoseph | ATE/5804/16 | Person 1 — Application Developer |
| Henok Zemedkun | ATE/8552/16 | Person 2 — Test Architect & Document Author |
| Eyob Kassaye | ATE/4534/16 | Person 3 — Test Automation Engineer & CI/CD |

---

## 1. Introduction

The Employee Leave Management System is a Flask/SQLite web application that lets employees
submit, track and cancel leave requests, and lets administrators approve or reject them.
The system enforces business rules on service length, request size, leave type, remaining
balance and supporting documents, and it governs each request through a five-state lifecycle.

This Test Plan defines what will be tested, how, by whom, in what order, and the criteria
that decide when testing starts and when it may stop. It is the controlling document for
all test activity on the project; the detailed cases it governs live in
[`test_design.md`](test_design.md), and its outcome is reported in
[`test_summary_report.md`](test_summary_report.md).

## 2. Test Items

| Item | Version / location | Included |
|---|---|---|
| `app/business_logic.py` — eligibility, balance, date validation, orchestration | branch `claude/leave-test-documentation-pr7424` | Yes |
| `app/models.py` — `Employee`, `LeaveRequest` (state machine), `LeaveBalance` | same | Yes |
| `app/routes.py` — login, dashboard, request, history, cancel, admin approve/reject | same | Yes |
| `app/auth.py` — password hashing, `login_required`, `admin_required` | same | Yes |
| `app/__init__.py` — app factory, DB schema | same | Yes |
| Jinja2 templates + `static/style.css` | same | Rendering only, no visual/CSS testing |

## 3. Scope

### 3.1 In scope

- **Functional correctness of the business rules**: the six-month service requirement, the
  1–30 day request range, the three valid leave types, the balance-sufficiency rule, and
  the supporting-document rule for sick leave over three days.
- **The leave request state machine**: every transition among `Requested`, `Approved`,
  `Rejected`, `Cancelled` and `Taken`, valid and invalid alike.
- **Date validation**: format, past start dates, inverted ranges, day-count arithmetic.
- **Balance arithmetic**: deduction on approval, restoration on cancellation, remaining-day
  calculation, behaviour when no balance record exists.
- **Access control at route level**: unauthenticated access, employee-versus-admin
  authorisation, cross-employee access to another person's request.
- **Integration between layers**: route → business logic → model → database.

### 3.2 Out of scope

| Excluded | Reason |
|---|---|
| Performance, load and stress testing | No stated non-functional requirement; single-user coursework deployment. |
| Security penetration testing (SQLi, XSS, CSRF) | Out of course scope. Noted as residual risk in the Test Summary Report. |
| Cross-browser and responsive/visual testing | Single reference browser agreed for system tests. |
| Database migration and upgrade testing | Schema is created once by `init_db`; no versioned migrations exist. |
| Localisation, accessibility, internationalisation | Not required by the specification. |
| Concurrency and multi-user race conditions | No locking requirement specified. The related single-user over-approval flaw **is** in scope and is recorded as DEF-002. |

## 4. Test Approach

Testing follows the four levels of the V-model, each mapped to the development artefact it verifies.

### 4.1 Unit testing

- **Target**: individual functions in `business_logic.py`, methods on `models.py`, and
  helpers in `auth.py`, in isolation from the database and HTTP layer.
- **Technique**: white-box, driven by the black-box case designs in `test_design.md`.
  Equivalence partitioning and boundary value analysis supply the input sets; branch
  coverage confirms nothing is left unexercised.
- **Test doubles**: a **fake** in-memory balance store replaces the DB; a **mock** replaces
  the request-creation call in `process_leave_request`; a **spy** wraps `get_balance` to
  assert call patterns while preserving real behaviour.
- **Tooling**: `pytest`, `unittest.mock`, `pytest-cov` with `--cov-branch`.
- **Owner**: Person 2 designs, Person 3 automates and maintains in CI.

### 4.2 Integration testing

- **Target**: route → business logic → model → SQLite, exercised through Flask's test client
  against a temporary database created per test.
- **Technique**: decision table testing for the rule combinations that cross layers, and
  state transition testing for the approve/reject/cancel flows, which only have meaning once
  the model and the database participate.
- **Tooling**: `pytest` with the `app`, `client`, `auth_client`, `admin_client`,
  `sample_employee`, `sample_admin` and `sample_balance` fixtures from `tests/conftest.py`.
- **Owner**: Person 2 designs and writes `test_decision_table.py` and
  `test_state_transitions.py`; Person 3 wires them into the pipeline.

### 4.3 System testing

- **Target**: the deployed application driven through a real browser, end to end.
- **Technique**: scenario-based testing of the primary user journeys — log in, submit a
  request, see it in history, have an admin approve it, see the balance change, cancel it.
  Page Object pattern to isolate locators from test logic.
- **Tooling**: Selenium WebDriver.
- **Owner**: Person 3.

### 4.4 User Acceptance Testing (UAT)

- **Target**: the business rules as an employee and an administrator would state them.
- **Technique**: manual, checklist-driven acceptance scenarios executed against a seeded
  demo database, verifying each rule in the README's "Business Rules" table produces the
  outcome a user expects, with a comprehensible message.
- **Entry**: system testing complete and all Critical/High defects closed or waived.
- **Owner**: whole team, with Person 2 recording results.

### 4.5 Regression testing

The full `pytest` suite runs on every push via GitHub Actions and on every Jenkins build.
Any defect fix must arrive with the test that reproduces it, and that test then joins the
regression set permanently.

## 5. Test Design Techniques

| Technique | Applied to | Rationale | Section in `test_design.md` |
|---|---|---|---|
| Equivalence Partitioning | days requested, leave type, service months, balance, dates | Reduces a very large input space to one representative per class of behaviour. | §2 |
| Boundary Value Analysis | 0/1/2 and 29/30/31 days; 5/6/7 service months; 3/4-day sick leave | Off-by-one errors cluster at boundaries; the code uses `<`, `>` and `>=` comparisons at each. | §3 |
| Decision Table Testing | the combined eligibility rule set | Five conditions interact; a decision table proves every combination has a defined, tested outcome and exposes gaps. | §4 |
| State Transition Testing | the leave request lifecycle | The status field is a five-state machine with an explicit transition map; both permitted and forbidden transitions need proof. | §5 |

## 6. Risk-Based Prioritisation

Risk = likelihood of failure × business impact. Priority P1 is tested first and most deeply.

| Risk ID | Risk | Likelihood | Impact | Priority | Mitigation in this plan |
|---|---|---|---|---|---|
| R1 | Balance corruption — an employee is credited or charged the wrong number of days | High | High | **P1** | Decision table §4 and state transition §5 both assert balance arithmetic after every transition; integration tests read the balance back from the database rather than trusting the response. |
| R2 | An ineligible employee obtains leave (service, range or balance rule bypassed) | Medium | High | **P1** | Full decision table coverage, every rule automated in `test_decision_table.py`. |
| R3 | Invalid state transition accepted — e.g. a rejected request later approved | Medium | High | **P1** | All 25 state pairs tested explicitly in `test_state_transitions.py`, 5 valid and 20 invalid. |
| R4 | Boundary off-by-one on the 1–30 day range or the 6-month rule | High | Medium | **P2** | Boundary value analysis §3, three points per boundary. |
| R5 | Sick-leave document rule not enforced | Medium | Medium | **P2** | Dedicated decision table rules R7–R9 plus the 3/4-day boundary pair. |
| R6 | Authorisation bypass — employee reaches admin functions, or acts on another employee's request | Low | High | **P2** | Route-level access control tests in `test_routes.py` (Person 3) and the cross-employee cancel case ST-INV-21. |
| R7 | Date validation gap — past or inverted ranges accepted | Medium | Medium | **P3** | Equivalence partitions and boundary cases on `validate_leave_dates`. |
| R8 | UI/template rendering error | Low | Low | **P3** | Covered incidentally by route and Selenium tests; no dedicated cases. |

Effort is allocated accordingly: roughly 60% of designed cases target P1 risks, 30% P2, 10% P3.

## 7. Entry Criteria

Testing at a given level may begin only when all of the following hold.

| # | Entry criterion | Applies to |
|---|---|---|
| E1 | The code under test is committed to the repository and the branch builds without error. | All levels |
| E2 | `pip install -r requirements.txt` completes and `pytest` collects the suite without collection errors. | All levels |
| E3 | The Test Plan and Test Design Document are reviewed and baselined. | All levels |
| E4 | `tests/conftest.py` provides the agreed fixtures and the temporary-database teardown works. | Unit, Integration |
| E5 | All unit tests pass and branch coverage of `business_logic.py` is at or above 80%. | Integration |
| E6 | Integration tests pass and the application starts successfully via `python run.py`. | System |
| E7 | System tests pass and no Critical or High defect is Open. | UAT |

## 8. Exit Criteria

Testing may stop when all of the following are satisfied, or when a deviation is formally
accepted and recorded in the Test Summary Report.

| # | Exit criterion | Target |
|---|---|---|
| X1 | Designed test cases executed | 100% |
| X2 | Test cases passed | ≥ 95% of executed, with every failure traced to a logged defect |
| X3 | Branch coverage of `app/business_logic.py` | ≥ 80% |
| X4 | Statement coverage of `app/` overall | ≥ 85% |
| X5 | Critical and High severity defects Open | 0 |
| X6 | Medium severity defects Open | ≤ 3, each with a documented workaround and accepted residual risk |
| X7 | Every decision table rule has at least one automated test | 100% of rules |
| X8 | Every valid and invalid state transition has at least one automated test | 25 of 25 pairs |
| X9 | All test documentation complete, reviewed and committed | Plan, Design, Defect Log, Metrics, Summary Report, Reflection |
| X10 | CI pipeline green on the final commit (excluding tests deliberately marked as defect reproducers) | Pass |

**Suspension and resumption.** Testing is suspended if a Critical defect blocks more than
30% of designed cases from executing, or if the build cannot start. It resumes once a fixed
build passes a smoke run of the login, submit and approve journeys.

## 9. Test Environment

| Element | Configuration |
|---|---|
| Language / runtime | Python 3.11 |
| Framework | Flask 3.1.1 |
| Database | SQLite — a fresh temporary file per test, created and deleted by the `app` fixture |
| Test framework | pytest 8.3.5, pytest-cov 6.1.1, `unittest.mock` |
| System test driver | Selenium WebDriver, Page Object pattern |
| CI | GitHub Actions on every push; Jenkins (Docker) with Setup → Unit → Integration → System stages |
| Test data | Seeded per test by fixtures: employee `test@company.com` (hired 2025-01-01), admin `admin@company.com`, balances Annual 20 / Sick 15 / Personal 5 |

## 10. Roles and Responsibilities

| Role | Person | Responsibilities |
|---|---|---|
| Application Developer | Fitsum Yoseph (ATE/5804/16) | Implements and maintains `app/`; fixes defects raised against it; supplies the code under test and keeps the build green at unit level. |
| Test Architect & Document Author | Henok Zemedkun (ATE/8552/16) | Owns this Test Plan, the Test Design Document, the Defect Log, the metrics, the Test Summary Report and the Foundations Reflection. Derives all test cases from the four techniques, writes `test_decision_table.py` and `test_state_transitions.py`, and reports defects. |
| Test Automation Engineer & CI/CD | Eyob Kassaye (ATE/4534/16) | Owns `tests/conftest.py` fixtures, the Selenium system tests, the GitHub Actions workflow and the Jenkins pipeline; keeps coverage reporting running and the pipeline maintained. |

**Independence note.** Test design and defect reporting sit with Person 2, who did not write
the application code. Every defect in `defect_log.csv` was found by testing rather than by
the author of the code under test, which is the separation this plan relies on.

## 11. Deliverables

| Deliverable | Location |
|---|---|
| Test Plan | `docs/test_plan.md` (and `docs/docx/test_plan.docx`) |
| Test Design Document | `docs/test_design.md` |
| Defect Log | `defect_log.csv` |
| Quality Metrics | `metrics.json` |
| Test Summary Report | `docs/test_summary_report.md` |
| Foundations Reflection | `docs/foundations_reflection.md` |
| Automated unit tests | `tests/test_business_logic.py`, `tests/test_routes.py` |
| Automated decision table tests | `tests/test_decision_table.py` |
| Automated state transition tests | `tests/test_state_transitions.py` |
| Coverage report | `htmlcov/` (generated) |

## 12. Schedule and Estimation

| Phase | Activity | Owner |
|---|---|---|
| 1 | Test planning, risk analysis, plan baseline | Person 2 |
| 2 | Test design: EP, BVA, decision table, state transition | Person 2 |
| 3 | Unit test implementation and test doubles | Persons 2, 3 |
| 4 | Integration test implementation (decision table, state transitions) | Person 2 |
| 5 | System tests (Selenium) and CI pipelines | Person 3 |
| 6 | Defect logging, retest, metrics collection | Person 2 |
| 7 | Test Summary Report, reflection, release recommendation | Person 2 |

## 13. Approvals

| Role | Name | Signature | Date |
|---|---|---|---|
| Test Architect | Henok Zemedkun | | |
| Application Developer | Fitsum Yoseph | | |
| Automation / CI Engineer | Eyob Kassaye | | |
