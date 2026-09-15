# Test Design Document — Employee Leave Management System

## Document Control

| Field | Value |
|---|---|
| Document | Test Design Document |
| Project | Employee Leave Management System |
| Course | Software Testing & Validation — Final Project |
| Version | 1.0 |
| Date | 2026-09-15 |
| Author | Henok Zemedkun (Person 2 — Test Architect & Document Author) |
| Governed by | [`test_plan.md`](test_plan.md) |

### Team Members

| Name | Student ID | Role |
|---|---|---|
| Fitsum Yoseph | ATE/5804/16 | Person 1 — Application Developer |
| Henok Zemedkun | ATE/8552/16 | Person 2 — Test Architect & Document Author |
| Eyob Kassaye | ATE/4534/16 | Person 3 — Test Automation Engineer & CI/CD |

---

## 1. Introduction

### 1.1 Purpose

This document derives the concrete test cases for the Employee Leave Management System from
four black-box test design techniques: equivalence partitioning, boundary value analysis,
decision table testing and state transition testing. Every case is listed with an ID, a
description, its preconditions, its steps and its expected result, so that any team member
can execute it by hand or trace it to its automated counterpart.

### 1.2 Specification under test

The rules being tested are taken from the README's business rules table and from the
docstrings in `app/business_logic.py`:

| Rule | Statement |
|---|---|
| BR-1 | An employee must have at least 6 months of service to take leave. |
| BR-2 | A leave request must be for between 1 and 30 days inclusive. |
| BR-3 | The leave type must be one of `Annual`, `Sick`, `Personal`. |
| BR-4 | The requested days must not exceed the remaining balance for that leave type. |
| BR-5 | Sick leave of more than 3 days requires a supporting document. |
| BR-6 | Dates must be well-formed, the start date must not be in the past, and the end date must be on or after the start date. |
| BR-7 | A leave request moves through the states `Requested → Approved / Rejected / Cancelled`, and `Approved → Taken / Cancelled`. All other transitions are forbidden. |
| BR-8 | Approving a request deducts the days from the balance; cancelling a request that had been deducted restores them. |

### 1.3 ID convention

| Prefix | Technique | Automated in |
|---|---|---|
| `EP-nn` | Equivalence partitioning | `tests/test_business_logic.py`, `tests/test_decision_table.py` |
| `BVA-nn` | Boundary value analysis | `tests/test_business_logic.py`, `tests/test_decision_table.py` |
| `DT-nn` | Decision table | `tests/test_decision_table.py` |
| `ST-Vnn` | State transition — valid | `tests/test_state_transitions.py` |
| `ST-Inn` | State transition — invalid | `tests/test_state_transitions.py` |
| `ST-Rnn` | State transition — route level | `tests/test_state_transitions.py` |

### 1.4 Standing preconditions

Unless a case says otherwise, every case assumes:

- **PRE-A** — A fresh application instance backed by an empty temporary SQLite database
  (the `app` fixture in `tests/conftest.py`).
- **PRE-B** — An employee `test@company.com` exists with `hire_date = 2025-01-01`, which is
  well over 6 months of service at the execution date (the `sample_employee` fixture).
- **PRE-C** — That employee holds balances Annual 20, Sick 15, Personal 5, all with
  `used_days = 0` (the `sample_balance` fixture).
- **PRE-D** — An administrator `admin@company.com` exists (the `sample_admin` fixture).

---

## 2. Equivalence Partitioning

### 2.1 Method

The input domain of each parameter is divided into classes whose members the specification
treats identically. One representative from each class is enough: if the representative
passes, the class is presumed covered; if it fails, the whole class is suspect. This reduces
an effectively infinite input space to a small, defensible set of cases.

### 2.2 Identified partitions

#### 2.2.1 `days_requested`

| Partition | Class | Range | Representative | Expected |
|---|---|---|---|---|
| P1 | Invalid — below minimum | `days < 1` (…, −5, 0) | 0 | Rejected: "Days requested must be at least 1" |
| P2 | **Valid** | `1 ≤ days ≤ 30` | 10 | Accepted (subject to the other rules) |
| P3 | Invalid — above maximum | `days > 30` (31, 45, 365) | 45 | Rejected: "Days requested cannot exceed 30" |
| P4 | Invalid — wrong type | not an integer (`'5'`, `5.5`, `None`, `True`) | `'5'` | Rejected: "Days requested must be at least 1" |

#### 2.2.2 `leave_type`

| Partition | Class | Members | Representative | Expected |
|---|---|---|---|---|
| P5 | **Valid** — Annual | `'Annual'` | `'Annual'` | Accepted, checked against the Annual balance |
| P6 | **Valid** — Sick | `'Sick'` | `'Sick'` | Accepted, additionally subject to BR-5 |
| P7 | **Valid** — Personal | `'Personal'` | `'Personal'` | Accepted, checked against the Personal balance |
| P8 | Invalid | anything else: `'Maternity'`, `'annual'`, `''`, `None`, `'ANNUAL'` | `'Maternity'` | Rejected: "Invalid leave type…" |

The comparison is case-sensitive, so `'annual'` belongs to the invalid partition P8, not to
P5. That is a deliberate sub-case worth its own representative because it is the most likely
real-world mistake in this class.

#### 2.2.3 `service_months` (derived from `hire_date`)

| Partition | Class | Range | Representative | Expected |
|---|---|---|---|---|
| P9 | Invalid — insufficient service | `0 ≤ months < 6` | 3 months | Rejected: "Minimum 6 months of service required…" |
| P10 | **Valid** — eligible | `months ≥ 6` | 24 months | Passes BR-1 |
| P11 | Invalid — future hire date | `hire_date > today` | tomorrow | `calculate_service_months` clamps to 0 → rejected by BR-1 |

#### 2.2.4 Balance

| Partition | Class | Condition | Representative | Expected |
|---|---|---|---|---|
| P12 | **Valid** — sufficient | `days ≤ remaining` | 10 days against 20 remaining | Passes BR-4 |
| P13 | Invalid — insufficient | `days > remaining` | 25 days against 20 remaining | Rejected: "Insufficient balance. Available: 20 days" |
| P14 | Invalid — no balance record | `get_balance` returns `None` | employee with no Personal row | Treated as 0 remaining → rejected |

#### 2.2.5 Supporting document

| Partition | Class | Condition | Expected |
|---|---|---|---|
| P15 | **Valid** — document not required | type ≠ Sick, any `has_document` | BR-5 does not apply; accepted |
| P16 | **Valid** — short sick leave | type = Sick, `days ≤ 3`, any `has_document` | BR-5 does not apply; accepted |
| P17 | **Valid** — long sick leave with document | type = Sick, `days > 3`, `has_document = True` | Accepted |
| P18 | Invalid — long sick leave without document | type = Sick, `days > 3`, `has_document = False` | Rejected: "Supporting document required for sick leave exceeding 3 days" |

#### 2.2.6 Dates

| Partition | Class | Condition | Representative | Expected |
|---|---|---|---|---|
| P19 | **Valid** | well-formed, `start ≥ today`, `end ≥ start` | start = today+5, end = today+9 | Valid, 5 days |
| P20 | Invalid — malformed | not `YYYY-MM-DD` | `'15/09/2026'`, `''`, `None` | Rejected: "Invalid date format. Use YYYY-MM-DD" |
| P21 | Invalid — past start | `start < today` | today−1 | Rejected: "Start date cannot be in the past" |
| P22 | Invalid — inverted range | `end < start` | start = today+5, end = today+3 | Rejected: "End date must be on or after start date" |

### 2.3 Equivalence partitioning test cases

| ID | Partition | Description | Preconditions | Steps | Expected result |
|---|---|---|---|---|---|
| EP-01 | P1 | Zero days is rejected as below the minimum | PRE-B, PRE-C | Call `check_eligibility(employee, 'Annual', 0, False)` | `(False, "Days requested must be at least 1")` |
| EP-02 | P1 | A negative day count is rejected | PRE-B, PRE-C | Call `check_eligibility(employee, 'Annual', -5, False)` | `(False, "Days requested must be at least 1")` |
| EP-03 | P2 | A mid-range day count is accepted | PRE-B, PRE-C | Call `check_eligibility(employee, 'Annual', 10, False)` | `(True, "Eligible")` |
| EP-04 | P3 | A day count above the maximum is rejected | PRE-B, PRE-C | Call `check_eligibility(employee, 'Annual', 45, False)` | `(False, "Days requested cannot exceed 30")` |
| EP-05 | P4 | A string day count is rejected as a wrong type | PRE-B, PRE-C | Call `check_eligibility(employee, 'Annual', '5', False)` | `(False, "Days requested must be at least 1")`; no `TypeError` is raised |
| EP-06 | P4 | A float day count is rejected as a wrong type | PRE-B, PRE-C | Call `check_eligibility(employee, 'Annual', 5.5, False)` | `(False, "Days requested must be at least 1")` |
| EP-07 | P5 | Annual leave within balance is accepted | PRE-B, PRE-C | Call `check_eligibility(employee, 'Annual', 10, False)` | `(True, "Eligible")`; the Annual balance of 20 is the one consulted |
| EP-08 | P6 | Sick leave of 3 days or fewer is accepted without a document | PRE-B, PRE-C | Call `check_eligibility(employee, 'Sick', 2, False)` | `(True, "Eligible")` |
| EP-09 | P7 | Personal leave within its smaller balance is accepted | PRE-B, PRE-C | Call `check_eligibility(employee, 'Personal', 5, False)` | `(True, "Eligible")`; the Personal balance of 5 is the one consulted |
| EP-10 | P8 | An unrecognised leave type is rejected | PRE-B, PRE-C | Call `check_eligibility(employee, 'Maternity', 5, False)` | `(False, "Invalid leave type. Must be one of: Annual, Sick, Personal")` |
| EP-11 | P8 | Leave type matching is case-sensitive | PRE-B, PRE-C | Call `check_eligibility(employee, 'annual', 5, False)` | `(False, "Invalid leave type…")` — lowercase is not accepted |
| EP-12 | P8 | An empty leave type is rejected | PRE-B, PRE-C | Call `check_eligibility(employee, '', 5, False)` | `(False, "Invalid leave type…")` |
| EP-13 | P9 | An employee with under 6 months of service is refused | Employee hired 3 months ago; PRE-C | Call `check_eligibility(employee, 'Annual', 5, False)` | `(False, "Minimum 6 months of service required. Current: 3 months")` |
| EP-14 | P10 | An employee with ample service passes the service rule | Employee hired 2 years ago; PRE-C | Call `check_eligibility(employee, 'Annual', 5, False)` | `(True, "Eligible")` |
| EP-15 | P11 | A future hire date yields zero service months | Employee with `hire_date` = tomorrow | Call `calculate_service_months(hire_date)` then `check_eligibility` | `calculate_service_months` returns `0`; eligibility is `(False, "Minimum 6 months of service required. Current: 0 months")` |
| EP-16 | P12 | A request within the remaining balance is accepted | PRE-B, PRE-C | Call `check_eligibility(employee, 'Annual', 10, False)` | `(True, "Eligible")` |
| EP-17 | P13 | A request exceeding the remaining balance is refused | PRE-B, PRE-C | Call `check_eligibility(employee, 'Annual', 25, False)` | `(False, "Insufficient balance. Available: 20 days")` |
| EP-18 | P14 | A missing balance record is treated as zero | Employee exists with **no** `leave_balance` row for Personal | Call `calculate_leave_balance(emp.id, 'Personal')`, then `check_eligibility(employee, 'Personal', 1, False)` | Balance is `0`; eligibility is `(False, "Insufficient balance. Available: 0 days")` |
| EP-19 | P15 | The document rule does not apply to non-sick leave | PRE-B, PRE-C | Call `check_eligibility(employee, 'Annual', 10, False)` | `(True, "Eligible")` — no document demanded for a 10-day Annual request |
| EP-20 | P17 | Long sick leave with a document is accepted | PRE-B, PRE-C | Call `check_eligibility(employee, 'Sick', 10, True)` | `(True, "Eligible")` |
| EP-21 | P18 | Long sick leave without a document is refused | PRE-B, PRE-C | Call `check_eligibility(employee, 'Sick', 10, False)` | `(False, "Supporting document required for sick leave exceeding 3 days")` |
| EP-22 | P19 | A well-formed future date range validates and counts days inclusively | PRE-A | Call `validate_leave_dates(today+5, today+9)` | `(True, "Valid dates", 5)` — both endpoints counted |
| EP-23 | P20 | A malformed date is rejected | PRE-A | Call `validate_leave_dates('15/09/2026', '20/09/2026')` | `(False, "Invalid date format. Use YYYY-MM-DD", 0)` |
| EP-24 | P20 | A `None` date is rejected without raising | PRE-A | Call `validate_leave_dates(None, None)` | `(False, "Invalid date format. Use YYYY-MM-DD", 0)` |
| EP-25 | P21 | A start date in the past is rejected | PRE-A | Call `validate_leave_dates(today−1, today+5)` | `(False, "Start date cannot be in the past", 0)` |
| EP-26 | P22 | An end date before the start date is rejected | PRE-A | Call `validate_leave_dates(today+5, today+3)` | `(False, "End date must be on or after start date", 0)` |

**Coverage.** 22 partitions, 26 cases, every partition represented at least once.

---

## 3. Boundary Value Analysis

### 3.1 Method

Partition boundaries are where `<`, `>`, `<=` and `>=` are written, and therefore where
off-by-one faults live. For each boundary the three-point method is used: the value just
below, the boundary value itself, and the value just above. The task brief calls for the
0/1/2, 29/30/31 and 5/6/7 sets; the balance and sick-document boundaries are added because
the same comparison risk exists there.

### 3.2 Boundaries identified

| Boundary | Code | Comparison | Points tested |
|---|---|---|---|
| B1 — minimum days | `business_logic.py:49` | `days_requested < 1` | 0, **1**, 2 |
| B2 — maximum days | `business_logic.py:52` | `days_requested > 30` | 29, **30**, 31 |
| B3 — service months | `business_logic.py:56` | `service_months < 6` | 5, **6**, 7 |
| B4 — sick document threshold | `business_logic.py:63` | `days_requested > 3` | 2, **3**, 4 |
| B5 — balance limit | `business_logic.py:60` | `days_requested > remaining` | remaining−1, **remaining**, remaining+1 |
| B6 — start date floor | `business_logic.py:80` | `start < date.today()` | today−1, **today**, today+1 |
| B7 — end date floor | `business_logic.py:83` | `end < start` | start−1, **start**, start+1 |

### 3.3 Boundary value test cases

| ID | Boundary | Description | Preconditions | Steps | Expected result |
|---|---|---|---|---|---|
| BVA-01 | B1 − | 0 days — just below the lower boundary | PRE-B, PRE-C | `check_eligibility(employee, 'Annual', 0, False)` | `(False, "Days requested must be at least 1")` |
| BVA-02 | B1 **on** | 1 day — the lower boundary itself, the smallest legal request | PRE-B, PRE-C | `check_eligibility(employee, 'Annual', 1, False)` | `(True, "Eligible")` |
| BVA-03 | B1 + | 2 days — just above the lower boundary | PRE-B, PRE-C | `check_eligibility(employee, 'Annual', 2, False)` | `(True, "Eligible")` |
| BVA-04 | B2 − | 29 days — just below the upper boundary | Employee with Annual balance ≥ 31 | `check_eligibility(employee, 'Annual', 29, False)` | `(True, "Eligible")` |
| BVA-05 | B2 **on** | 30 days — the upper boundary itself, the largest legal request | Employee with Annual balance ≥ 31 | `check_eligibility(employee, 'Annual', 30, False)` | `(True, "Eligible")` |
| BVA-06 | B2 + | 31 days — just above the upper boundary | Employee with Annual balance ≥ 31 | `check_eligibility(employee, 'Annual', 31, False)` | `(False, "Days requested cannot exceed 30")` — rejected on the range rule, **not** on balance |
| BVA-07 | B3 − | 5 months of service — just below the threshold | Employee hired exactly 5 months ago; PRE-C | `check_eligibility(employee, 'Annual', 5, False)` | `(False, "Minimum 6 months of service required. Current: 5 months")` |
| BVA-08 | B3 **on** | 6 months of service — the threshold itself, the first eligible day | Employee hired exactly 6 months ago; PRE-C | `check_eligibility(employee, 'Annual', 5, False)` | `(True, "Eligible")` |
| BVA-09 | B3 + | 7 months of service — just above the threshold | Employee hired exactly 7 months ago; PRE-C | `check_eligibility(employee, 'Annual', 5, False)` | `(True, "Eligible")` |
| BVA-10 | B3 | `calculate_service_months` returns exactly 6 at the 6-month mark | none | `calculate_service_months(today − 6 months)` | `6` |
| BVA-11 | B3 | Service months are clamped at zero, never negative | none | `calculate_service_months(today + 30 days)` | `0` |
| BVA-12 | B4 − | 2-day sick leave without a document — below the document threshold | PRE-B, PRE-C | `check_eligibility(employee, 'Sick', 2, False)` | `(True, "Eligible")` |
| BVA-13 | B4 **on** | 3-day sick leave without a document — exactly at the threshold, still allowed | PRE-B, PRE-C | `check_eligibility(employee, 'Sick', 3, False)` | `(True, "Eligible")` — the rule is *exceeding* 3 days |
| BVA-14 | B4 + | 4-day sick leave without a document — just over the threshold | PRE-B, PRE-C | `check_eligibility(employee, 'Sick', 4, False)` | `(False, "Supporting document required for sick leave exceeding 3 days")` |
| BVA-15 | B4 + | 4-day sick leave **with** a document is accepted | PRE-B, PRE-C | `check_eligibility(employee, 'Sick', 4, True)` | `(True, "Eligible")` |
| BVA-16 | B5 − | Requesting one day less than the balance | PRE-B, PRE-C (Annual 20) | `check_eligibility(employee, 'Annual', 19, False)` | `(True, "Eligible")` |
| BVA-17 | B5 **on** | Requesting exactly the whole remaining balance | PRE-B, PRE-C (Annual 20) | `check_eligibility(employee, 'Annual', 20, False)` | `(True, "Eligible")` — the comparison is strictly greater-than |
| BVA-18 | B5 + | Requesting one day more than the balance | PRE-B, PRE-C (Annual 20) | `check_eligibility(employee, 'Annual', 21, False)` | `(False, "Insufficient balance. Available: 20 days")` |
| BVA-19 | B5 **on** | Exhausted balance — zero remaining, one day requested | Employee whose Personal balance is fully used (`remaining = 0`) | `check_eligibility(employee, 'Personal', 1, False)` | `(False, "Insufficient balance. Available: 0 days")` |
| BVA-20 | B6 − | Start date yesterday — just below the floor | PRE-A | `validate_leave_dates(today−1, today+5)` | `(False, "Start date cannot be in the past", 0)` |
| BVA-21 | B6 **on** | Start date today — the floor itself, allowed | PRE-A | `validate_leave_dates(today, today+2)` | `(True, "Valid dates", 3)` |
| BVA-22 | B6 + | Start date tomorrow — just above the floor | PRE-A | `validate_leave_dates(today+1, today+3)` | `(True, "Valid dates", 3)` |
| BVA-23 | B7 − | End date one day before the start | PRE-A | `validate_leave_dates(today+5, today+4)` | `(False, "End date must be on or after start date", 0)` |
| BVA-24 | B7 **on** | End date equal to the start — a single-day request | PRE-A | `validate_leave_dates(today+5, today+5)` | `(True, "Valid dates", 1)` — a one-day leave, not zero |
| BVA-25 | B7 + | End date one day after the start | PRE-A | `validate_leave_dates(today+5, today+6)` | `(True, "Valid dates", 2)` |
| BVA-26 | B2 ∘ B7 | A 30-day range end-to-end through the orchestrator sits exactly on the limit | Employee with Annual balance ≥ 30 | `process_leave_request(employee, 'Annual', today+1, today+30, …)` | `validate_leave_dates` computes 30 days; the request succeeds |
| BVA-27 | B2 ∘ B7 | A 31-day range end-to-end through the orchestrator breaches the limit | Employee with Annual balance ≥ 31 | `process_leave_request(employee, 'Annual', today+1, today+31, …)` | `(False, "Days requested cannot exceed 30", None)`; no request is created |

**Coverage.** 7 boundaries, 3 points each where applicable, 27 cases.

---

## 4. Decision Table Testing

### 4.1 Method

Five conditions govern whether a leave request is accepted, and they interact: the outcome
of one depends on the values of the others, and the code evaluates them in a fixed
precedence order. Equivalence partitioning alone would test each condition in isolation and
miss the combinations. A decision table enumerates the combinations, assigns each an action,
and proves that every rule is reachable, unambiguous and tested.

The raw table has 2⁵ = 32 combinations (six conditions, but C5 is derived from C1 and the
day count, so it is not free). Because `check_eligibility` returns at the first failing
rule, later conditions become *don't care* once an earlier one fails. Collapsing on that
precedence reduces the table to **9 rules**, each of which is directly executable.

### 4.2 Conditions and actions

**Conditions**

| ID | Condition | Source |
|---|---|---|
| C1 | `leave_type` is one of Annual / Sick / Personal | BR-3, `business_logic.py:46` |
| C2 | `1 ≤ days_requested ≤ 30` and `days_requested` is an integer | BR-2, `business_logic.py:49,52` |
| C3 | `service_months ≥ 6` | BR-1, `business_logic.py:56` |
| C4 | `days_requested ≤ remaining balance` | BR-4, `business_logic.py:60` |
| C5 | A document is required — i.e. `leave_type == 'Sick'` **and** `days_requested > 3` | BR-5, `business_logic.py:63` |
| C6 | `has_document` is true | BR-5, `business_logic.py:63` |

**Actions**

| ID | Action | Returned value |
|---|---|---|
| A1 | Accept the request | `(True, "Eligible")` |
| A2 | Reject — invalid leave type | `(False, "Invalid leave type. Must be one of: Annual, Sick, Personal")` |
| A3 | Reject — below the minimum day count | `(False, "Days requested must be at least 1")` |
| A4 | Reject — above the maximum day count | `(False, "Days requested cannot exceed 30")` |
| A5 | Reject — insufficient service | `(False, "Minimum 6 months of service required. Current: N months")` |
| A6 | Reject — insufficient balance | `(False, "Insufficient balance. Available: N days")` |
| A7 | Reject — supporting document required | `(False, "Supporting document required for sick leave exceeding 3 days")` |

`—` means *don't care*: the rule has already been decided by an earlier condition, so the
value of this one cannot change the outcome.

### 4.3 The decision table

| | **R1** | **R2** | **R3** | **R4** | **R5** | **R6** | **R7** | **R8** | **R9** |
|---|---|---|---|---|---|---|---|---|---|
| **C1** type valid | N | Y | Y | Y | Y | Y | Y | Y | Y |
| **C2a** days ≥ 1 | — | N | Y | Y | Y | Y | Y | Y | Y |
| **C2b** days ≤ 30 | — | — | N | Y | Y | Y | Y | Y | Y |
| **C3** service ≥ 6 months | — | — | — | N | Y | Y | Y | Y | Y |
| **C4** balance sufficient | — | — | — | — | N | Y | Y | Y | Y |
| **C5** document required | — | — | — | — | — | Y | Y | N | N |
| **C6** document supplied | — | — | — | — | — | N | Y | N | Y |
| | | | | | | | | | |
| **A1** accept | | | | | | | ✔ | ✔ | ✔ |
| **A2** invalid type | ✔ | | | | | | | | |
| **A3** days below minimum | | ✔ | | | | | | | |
| **A4** days above maximum | | | ✔ | | | | | | |
| **A5** insufficient service | | | | ✔ | | | | | |
| **A6** insufficient balance | | | | | ✔ | | | | |
| **A7** document required | | | | | | ✔ | | | |

**Reading the table.** Rules R1–R6 are the six distinct ways a request can be refused, in
the precedence order the implementation applies them. Rules R7–R9 are the three ways it can
be accepted: long sick leave with a document (R7), a request to which the document rule does
not apply and no document was supplied (R8), and the same with a document supplied anyway
(R9). R8 and R9 together prove that `has_document` is correctly ignored when C5 is false —
a redundant-looking pair that exists precisely to catch a fault where the flag is consulted
unconditionally.

**Rule completeness.** Every combination of the six conditions falls into exactly one rule,
and no two rules can fire for the same input, so the table is both complete and consistent.

### 4.4 Decision table test cases

Each rule below becomes one or more automated tests in `tests/test_decision_table.py`.

| ID | Rule | Description | Preconditions | Steps | Expected result |
|---|---|---|---|---|---|
| DT-01 | R1 | An invalid leave type is refused before any other condition is considered | PRE-B, PRE-C | Call `check_eligibility(employee, 'Maternity', 5, False)` | `(False, "Invalid leave type. Must be one of: Annual, Sick, Personal")` |
| DT-02 | R1 | Type precedence — an invalid type wins even when every other condition also fails | Employee hired 1 month ago, **no** balance record | Call `check_eligibility(employee, 'Maternity', 99, False)` | A2 is returned, not A4 or A5 — the message names the leave type |
| DT-03 | R2 | A day count below the minimum is refused | PRE-B, PRE-C | Call `check_eligibility(employee, 'Annual', 0, False)` | `(False, "Days requested must be at least 1")` |
| DT-04 | R2 | Day-range precedence over the service rule | Employee hired 1 month ago; PRE-C | Call `check_eligibility(employee, 'Annual', 0, False)` | A3 is returned, not A5 |
| DT-05 | R3 | A day count above the maximum is refused | Employee with Annual balance 40 | Call `check_eligibility(employee, 'Annual', 31, False)` | `(False, "Days requested cannot exceed 30")` |
| DT-06 | R3 | Day-range precedence over the balance rule | PRE-B, PRE-C (Annual 20) | Call `check_eligibility(employee, 'Annual', 35, False)` | A4 is returned, not A6 — 35 exceeds both the range and the balance, and the range is checked first |
| DT-07 | R4 | Insufficient service is refused | Employee hired 2 months ago; PRE-C | Call `check_eligibility(employee, 'Annual', 5, False)` | `(False, "Minimum 6 months of service required. Current: 2 months")` |
| DT-08 | R4 | Service precedence over the balance rule | Employee hired 2 months ago, Annual balance 1 | Call `check_eligibility(employee, 'Annual', 5, False)` | A5 is returned, not A6 |
| DT-09 | R5 | Insufficient balance is refused | PRE-B, PRE-C (Annual 20) | Call `check_eligibility(employee, 'Annual', 25, False)` | `(False, "Insufficient balance. Available: 20 days")` |
| DT-10 | R5 | Balance precedence over the document rule | Employee with Sick balance 5 | Call `check_eligibility(employee, 'Sick', 10, False)` | A6 is returned, not A7 — both rules are breached, and balance is checked first |
| DT-11 | R6 | Long sick leave without a document is refused | PRE-B, PRE-C (Sick 15) | Call `check_eligibility(employee, 'Sick', 10, False)` | `(False, "Supporting document required for sick leave exceeding 3 days")` |
| DT-12 | R7 | Long sick leave with a document is accepted | PRE-B, PRE-C (Sick 15) | Call `check_eligibility(employee, 'Sick', 10, True)` | `(True, "Eligible")` |
| DT-13 | R8 | Annual leave, no document supplied and none required, is accepted | PRE-B, PRE-C | Call `check_eligibility(employee, 'Annual', 10, False)` | `(True, "Eligible")` |
| DT-14 | R8 | Short sick leave with no document is accepted | PRE-B, PRE-C | Call `check_eligibility(employee, 'Sick', 3, False)` | `(True, "Eligible")` |
| DT-15 | R8 | Personal leave with no document is accepted | PRE-B, PRE-C (Personal 5) | Call `check_eligibility(employee, 'Personal', 5, False)` | `(True, "Eligible")` |
| DT-16 | R9 | A document supplied where none is required is ignored, not penalised | PRE-B, PRE-C | Call `check_eligibility(employee, 'Annual', 10, True)` | `(True, "Eligible")` — identical to DT-13 |
| DT-17 | R9 | Short sick leave with a document is accepted | PRE-B, PRE-C | Call `check_eligibility(employee, 'Sick', 3, True)` | `(True, "Eligible")` |
| DT-18 | R8 ≡ R9 | The `has_document` flag makes no difference when C5 is false | PRE-B, PRE-C | Call `check_eligibility(employee, 'Personal', 5, False)` and `check_eligibility(employee, 'Personal', 5, True)` | The two results are identical |
| DT-19 | R2 (ext.) | **Defect probe — DEF-003.** A boolean day count is a wrong type, not a 1-day request | Service-eligible employee, sufficient balance | Call `check_eligibility(employee, 'Annual', True, False)` | *Specified:* `(False, "Days requested must be at least 1")`. *Observed:* `(True, "Eligible")` — **fails**, see DEF-003 |
| DT-20 | R4 (ext.) | **Defect probe — DEF-004.** A 31st-of-the-month hire date reaches 6 months on the last day of a short month | `hire_date = 2024-08-31`, evaluated on 2025-02-28 | Patch `date.today()` to 2025-02-28 and call `calculate_service_months('2024-08-31')` | *Specified:* `6`. *Observed:* `5`, so R4 fires and the employee is wrongly refused — **fails**, see DEF-004 |
| DT-21 | R5 (ext.) | Rule R5 is evaluated against the **remaining** balance, not the total | Employee whose Annual balance is 20 total with 15 already used (remaining 5) | Call `check_eligibility(employee, 'Annual', 10, False)` | `(False, "Insufficient balance. Available: 5 days")` |
| DT-22 | end-to-end | Each rule holds through the full orchestrator, not only at unit level | PRE-B, PRE-C | Call `process_leave_request` once per rule with dates producing the required day count | The message matches the rule's action, and a request object is created only for R7–R9 |

**Coverage.** 9 rules, 22 cases, every rule exercised at least twice, plus four
precedence cases (DT-02, DT-04, DT-06, DT-08, DT-10) that prove the ordering itself.

---

## 5. State Transition Testing

### 5.1 Method

A leave request's `status` is a finite state machine with five states and an explicit
transition map in `LeaveRequest.VALID_TRANSITIONS`. State transition testing derives cases
from the machine rather than from the input data: one case per permitted transition to show
it works, and one per forbidden transition to show it is actually refused. With 5 states
there are 5 × 5 = 25 ordered pairs, of which **5 are valid** and **20 are invalid** —
including the self-transitions, which are forbidden in every state.

### 5.2 States

| ID | State | Meaning | Kind |
|---|---|---|---|
| S1 | `Requested` | Submitted by the employee, awaiting an administrator's decision. No balance has been deducted. | Initial |
| S2 | `Approved` | An administrator approved it; the days have been deducted from the balance. | Intermediate |
| S3 | `Rejected` | An administrator refused it. No balance change. | Final |
| S4 | `Cancelled` | Withdrawn by the employee, from either `Requested` or `Approved`. | Final |
| S5 | `Taken` | The approved leave has been consumed. | Final |

### 5.3 Events

| ID | Event | Actor | Implementation |
|---|---|---|---|
| E1 | Approve | Administrator | `POST /admin/approve/<id>` → `update_status('Approved', admin_id)` |
| E2 | Reject | Administrator | `POST /admin/reject/<id>` → `update_status('Rejected', admin_id)` |
| E3 | Cancel | Owning employee | `POST /cancel/<id>` → `update_status('Cancelled')` |
| E4 | Mark taken | — | `update_status('Taken')`. **No caller exists in the application** — see DEF-005. |

### 5.4 State transition table

Rows are the current state, columns the target state. `✔` = permitted, `✘` = refused with
`"Cannot transition from X to Y"`.

| From \ To | **Requested** | **Approved** | **Rejected** | **Cancelled** | **Taken** |
|---|---|---|---|---|---|
| **Requested** | ✘ | ✔ | ✔ | ✔ | ✘ |
| **Approved** | ✘ | ✘ | ✘ | ✔ | ✔ |
| **Rejected** | ✘ | ✘ | ✘ | ✘ | ✘ |
| **Cancelled** | ✘ | ✘ | ✘ | ✘ | ✘ |
| **Taken** | ✘ | ✘ | ✘ | ✘ | ✘ |

### 5.5 State transition diagram

```
                            ┌──────────────┐
             approve        │              │        reject
        ┌──────────────────►│   APPROVED   │◄────────────────┐
        │                   │     (S2)     │                 │
        │                   └───┬──────┬───┘                 │
        │                       │      │                     │
┌───────┴───────┐        cancel │      │ mark taken   ┌──────┴───────┐
│   REQUESTED   │               │      │              │   REJECTED   │
│   (S1, init)  ├───────────────┼──────┼─────────────►│  (S3, final) │
└───────┬───────┘   reject      │      │              └──────────────┘
        │                       │      │
        │ cancel                ▼      ▼
        │               ┌──────────────┐   ┌──────────────┐
        └──────────────►│  CANCELLED   │   │    TAKEN     │
                        │  (S4, final) │   │  (S5, final) │
                        └──────────────┘   └──────────────┘

  S3, S4 and S5 are terminal: every outgoing transition is refused.
  The Approved → Taken edge is declared but never exercised (DEF-005).
```

### 5.6 Valid transition test cases

| ID | Transition | Description | Preconditions | Steps | Expected result |
|---|---|---|---|---|---|
| ST-V01 | S1 → S2 | An administrator approves a pending request | PRE-A–D; a request exists in `Requested` | 1. Load the request. 2. Call `can_transition_to('Approved')`. 3. Call `update_status('Approved', admin.id)`. 4. Re-read the request from the database. | Step 2 is `True`; step 3 returns `(True, "Status updated")`; the persisted status is `Approved` and `reviewed_by` is the admin's id |
| ST-V02 | S1 → S3 | An administrator rejects a pending request | as above | Same, targeting `Rejected` | `(True, "Status updated")`; the persisted status is `Rejected` |
| ST-V03 | S1 → S4 | The employee cancels a request still awaiting a decision | as above | Same, targeting `Cancelled` | `(True, "Status updated")`; the persisted status is `Cancelled` |
| ST-V04 | S2 → S4 | The employee cancels an already-approved leave | A request in `Approved` | Call `update_status('Cancelled')` | `(True, "Status updated")`; the persisted status is `Cancelled` |
| ST-V05 | S2 → S5 | An approved leave is marked as taken | A request in `Approved` | Call `update_status('Taken')` | `(True, "Status updated")`; the persisted status is `Taken`. The transition is permitted by the model, but nothing in the application ever triggers it — DEF-005 |

### 5.7 Invalid transition test cases

Every case has the same shape, so the preconditions, steps and expected result are stated
once and the table lists the 20 pairs.

- **Preconditions** — PRE-A–D, and a leave request whose `status` has been set to the *From*
  state (created in `Requested` and advanced through legal transitions, or written directly
  for the terminal states).
- **Steps** — 1. Load the request. 2. Assert `can_transition_to(<To>)` is `False`.
  3. Call `update_status(<To>)`. 4. Re-read the request from the database.
- **Expected result** — step 2 is `False`; step 3 returns
  `(False, "Cannot transition from <From> to <To>")`; the persisted status is **unchanged**
  and still the *From* state; no balance is altered.

| ID | From | To | Why it must be refused |
|---|---|---|---|
| ST-I01 | Requested | Requested | A request cannot be re-submitted over itself; a self-transition would clear `reviewed_by` and reset the audit trail. |
| ST-I02 | Requested | Taken | Leave cannot be taken before it has been approved. |
| ST-I03 | Approved | Requested | An approved request cannot be returned to the pending queue; the balance has already been deducted. |
| ST-I04 | Approved | Approved | Re-approval would deduct the balance a second time. |
| ST-I05 | Approved | Rejected | A decision already made cannot be reversed to the opposite decision; the correct route is cancellation. |
| ST-I06 | Rejected | Requested | `Rejected` is terminal; a new request must be raised instead. |
| ST-I07 | Rejected | Approved | A rejected request must never be silently approved — this is the highest-impact invalid transition. |
| ST-I08 | Rejected | Rejected | Terminal self-transition. |
| ST-I09 | Rejected | Cancelled | Nothing remains to cancel. |
| ST-I10 | Rejected | Taken | Rejected leave cannot be taken. |
| ST-I11 | Cancelled | Requested | `Cancelled` is terminal; a new request must be raised instead. |
| ST-I12 | Cancelled | Approved | A withdrawn request must not be approvable, which would deduct the balance after it was restored. |
| ST-I13 | Cancelled | Rejected | Nothing remains to decide. |
| ST-I14 | Cancelled | Cancelled | Terminal self-transition; would restore the balance twice (compare DEF-001). |
| ST-I15 | Cancelled | Taken | Cancelled leave cannot be taken. |
| ST-I16 | Taken | Requested | `Taken` is terminal; leave already consumed. |
| ST-I17 | Taken | Approved | Already consumed leave cannot be re-approved. |
| ST-I18 | Taken | Rejected | Already consumed leave cannot be retrospectively refused. |
| ST-I19 | Taken | Cancelled | Leave already consumed cannot be cancelled; the balance must not be restored. |
| ST-I20 | Taken | Taken | Terminal self-transition. |

### 5.8 Route-level and path test cases

The model enforces the machine; these cases prove the application drives it correctly and
keeps the balance consistent along each path.

| ID | Path / concern | Description | Preconditions | Steps | Expected result |
|---|---|---|---|---|---|
| ST-R01 | S1 → S2 via HTTP | Approval through the admin route persists the new state | PRE-A–D; a `Requested` request for 5 Annual days | 1. Log in as the administrator. 2. `POST /admin/approve/<id>`. 3. Re-read the request. | Redirect to `/admin`; the status is `Approved`; `reviewed_by` is the admin's id |
| ST-R02 | S1 → S3 via HTTP | Rejection through the admin route persists the new state | as above | `POST /admin/reject/<id>` | Status is `Rejected`; the balance is untouched (`used_days` still 0) |
| ST-R03 | S1 → S4 via HTTP | Cancellation through the employee route persists the new state | as above | Log in as the owning employee; `POST /cancel/<id>` | Status is `Cancelled` |
| ST-R04 | Balance on approval | Approving deducts exactly the requested days | PRE-A–D; a `Requested` request for 5 Annual days; Annual 20/0 | Approve via the admin route, then read `leave_balance` | `used_days = 5`, `remaining_days = 15` |
| ST-R05 | Balance on reject | Rejecting changes no balance | as ST-R04 | Reject via the admin route, then read `leave_balance` | `used_days = 0`, `remaining_days = 20` |
| ST-R06 | Full path S1→S2→S4 | Cancelling an approved leave returns the deducted days exactly once | as ST-R04 | 1. Approve (used becomes 5). 2. Log in as the employee. 3. `POST /cancel/<id>`. 4. Read the balance. | Status is `Cancelled`; `used_days` is back to 0 and `remaining_days` back to 20 — restored once, not twice |
| ST-R07 | Invalid path via HTTP | An approved request cannot be approved a second time through the route | A request already in `Approved`; Annual `used_days = 5` | `POST /admin/approve/<id>` again; read the balance | The transition is refused, a danger flash is shown, the status stays `Approved`, and `used_days` stays 5 — **not** 10 |
| ST-R08 | Invalid path via HTTP | A rejected request cannot then be approved through the route | A request already in `Rejected` | `POST /admin/approve/<id>` | Refused; the status stays `Rejected`; no balance change |
| ST-R09 | Authorisation | An employee cannot cancel another employee's request | Two employees; a `Requested` request owned by the first | Log in as the second employee; `POST /cancel/<first employee's request id>` | "Unauthorized action." is flashed; the status stays `Requested` |
| ST-R10 | Missing entity | Acting on a non-existent request is handled, not crashed | PRE-A–D | `POST /cancel/99999` as an employee and `POST /admin/approve/99999` as the administrator | Both redirect with "Leave request not found."; no exception (HTTP 500) is raised |
| ST-R11 | Guard | `can_transition_to` agrees with `update_status` for all 25 pairs | PRE-A–D | For every ordered pair, compare `can_transition_to(to)` with the success flag from `update_status(to)` | They agree for all 25 pairs — the guard is not bypassable |
| ST-R12 | **Defect probe — DEF-001** | Cancelling a request that was never approved must not credit the balance | PRE-A–D; a `Requested` request for 5 Annual days; Annual 20/0 | 1. `POST /cancel/<id>` as the owning employee without any approval. 2. Read `leave_balance`. | *Specified:* `used_days = 0`, `remaining_days = 20`. *Observed:* `used_days = -5`, `remaining_days = 25` — **fails**, see DEF-001 |
| ST-R13 | **Defect probe — DEF-002** | Approval must re-check the balance so that pending requests cannot be over-approved | Employee with Annual 20/0 and two separate 20-day `Requested` requests | 1. Approve both through the admin route. 2. Read `leave_balance`. | *Specified:* the second approval is refused; `used_days ≤ 20`. *Observed:* both approved, `used_days = 40`, `remaining_days = -20` — **fails**, see DEF-002 |
| ST-R14 | **Defect probe — DEF-005** | The `Taken` state must be reachable from the running application | PRE-A–D; a request in `Approved` | Search `app/` for any caller that sets the status to `Taken`; drive the application and attempt to reach `Taken` | *Specified:* some route, admin action or scheduled job moves an elapsed approved leave to `Taken`. *Observed:* no caller exists — **fails**, see DEF-005 |

**Coverage.** 25 of 25 ordered state pairs (5 valid, 20 invalid), plus 14 route-level and
path cases, of which 3 are defect probes.

---

## 6. Traceability

| Business rule | Techniques applied | Case IDs |
|---|---|---|
| BR-1 service ≥ 6 months | EP, BVA, Decision table | EP-13–15, BVA-07–11, DT-07, DT-08, DT-20 |
| BR-2 1–30 days | EP, BVA, Decision table | EP-01–06, BVA-01–06, BVA-26, BVA-27, DT-03–06, DT-19 |
| BR-3 valid leave type | EP, Decision table | EP-07–12, DT-01, DT-02 |
| BR-4 sufficient balance | EP, BVA, Decision table | EP-16–18, BVA-16–19, DT-09, DT-10, DT-21 |
| BR-5 sick-leave document | EP, BVA, Decision table | EP-19–21, BVA-12–15, DT-11, DT-12, DT-16–18 |
| BR-6 date validity | EP, BVA | EP-22–26, BVA-20–25 |
| BR-7 state transitions | State transition | ST-V01–V05, ST-I01–I20, ST-R01–R03, ST-R07, ST-R08, ST-R11, ST-R14 |
| BR-8 balance on approve/cancel | State transition | ST-R04–R06, ST-R12, ST-R13 |

**Totals.** 26 equivalence partitioning cases, 27 boundary value cases, 22 decision table
cases, 39 state transition cases — **114 designed cases**, of which 5 are defect probes
that are expected to fail against the current build.
