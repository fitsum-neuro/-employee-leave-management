# Foundations Reflection — Error, Fault and Failure

## Document Control

| Field | Value |
|---|---|
| Document | Foundations Reflection |
| Project | Employee Leave Management System |
| Course | Software Testing & Validation — Final Project |
| Version | 1.0 |
| Date | 2026-09-15 |
| Author | Henok Zemedkun (Person 2 — Test Architect & Document Author) |
| Subject defect | DEF-001 (`defect_log.csv`) |

### Team Members

| Name | Student ID | Role |
|---|---|---|
| Fitsum Yoseph | ATE/5804/16 | Person 1 — Application Developer |
| Henok Zemedkun | ATE/8552/16 | Person 2 — Test Architect & Document Author |
| Eyob Kassaye | ATE/4534/16 | Person 3 — Test Automation Engineer & CI/CD |

---

## 1. The three terms

The course distinguishes three things that everyday speech runs together as "a bug".

| Term | Definition | Where it lives |
|---|---|---|
| **Error** (mistake) | A human action that produces an incorrect result — a misunderstanding, a slip, a wrong assumption. | In a person's head |
| **Fault** (defect) | The flaw in the work product that the error caused — the wrong line of code, the missing condition, the incorrect requirement. | In the artefact |
| **Failure** | The observable deviation from expected behaviour when the fault is executed under the conditions that expose it. | In the running system |

The chain runs one way: an error *causes* a fault, and a fault *may cause* a failure. A
fault that is never executed under exposing conditions causes no failure at all and sits
latent. This is exactly why test design technique matters more than test quantity: a test
suite can execute a faulty line a thousand times and never see a failure if it never
supplies the state that makes the fault matter.

## 2. The defect: DEF-001

**Cancelling a leave request that is still in the `Requested` state credits the employee
with days that were never deducted.**

Reproduced by `tests/test_state_transitions.py::TestStateTransitionDefectProbes::test_st_r12_cancelling_a_requested_leave_must_not_credit_the_balance`.

I chose this one rather than DEF-002 because its chain is cleaner: the error is a single
identifiable piece of reasoning, the fault is four lines of code, and the failure is a
number that is visibly, arithmetically impossible — a negative count of days used.

### 2.1 The error — in the developer's reasoning

The application has two balance-moving operations that look like mirror images:

- approving a request **deducts** the days, and
- cancelling a request **restores** them.

The error was to treat that symmetry as complete — to think of "cancel" as *one* event that
always undoes *one* deduction. It is a reasonable-sounding piece of reasoning and it is
wrong, because cancellation is not one transition. The state machine in `models.py` allows
two:

- `Requested → Cancelled`, where **nothing has been deducted yet**, and
- `Approved → Cancelled`, where the days **were** deducted at approval.

Only the second has anything to give back. The mistake was reasoning about the *event*
("the user cancelled") instead of the *transition* ("the user cancelled **from which
state**"). The state machine had already made that distinction explicit, one file away, and
the handler simply did not consult it.

Notably, the same developer got the harder half right: approval is the only place that
deducts, and it deducts exactly once. The error was not carelessness about balances in
general. It was a specific missing case in a specific direction.

### 2.2 The fault — in `app/routes.py:95-99`

```python
success, msg = leave_req.update_status('Cancelled')
if success:
    if leave_req.status == 'Cancelled' and leave_req.days_requested:
        LeaveBalance.restore(leave_req.employee_id, leave_req.leave_type,
                             leave_req.days_requested)
```

The fault is the condition on line 97. It *looks* like a safety check, which is what makes
it worth studying, but it guards nothing:

1. `update_status` sets `self.status = new_status` on success, so by the time line 97 runs,
   `leave_req.status` **is** `'Cancelled'` — the comparison is a tautology.
2. `days_requested` is `NOT NULL` in the schema and is always at least 1 for any request
   that exists, so the second operand is always truthy.

The condition is therefore always true, and `restore` runs on every successful
cancellation. The guard that *should* be there tests the status **before** the transition:

```python
previous_status = leave_req.status          # capture before the transition
success, msg = leave_req.update_status('Cancelled')
if success and previous_status == 'Approved':
    LeaveBalance.restore(...)
```

Two details make this fault characteristic of its type. First, the fault is an **omission**
— a missing condition, not a wrong one — and omissions are the hardest faults to see when
reading code, because there is nothing on the page to look wrong. Second, `LeaveBalance.restore`
does a bare `used_days = used_days - ?` with no floor at zero, so nothing downstream catches
the impossible value either. A single missing guard produces an unchecked corruption.

There is a measurable trace of this fault in the coverage report. `app/routes.py:97->100`
is the only branch in the whole application that our suite cannot cover, because the false
arm of a tautology is unreachable. **An uncoverable branch is a smell**: it says a condition
cannot discriminate, which is another way of saying it is not really a condition. Coverage
tooling pointed at the fault without knowing why — and only after a targeted test had
already found it.

### 2.3 The failure — observed behaviour

Arrange an employee with an Annual balance of 20 days, none used.

| Step | Action | `used_days` | `remaining_days` |
|---|---|---|---|
| 1 | Submit a 5-day Annual request. Status `Requested`; nothing is deducted. | 0 | 20 |
| 2 | `POST /cancel/<id>` before any administrator has acted. | **−5** | **25** |

The failure is `used_days = -5`: the employee has used *negative five days* of leave, and
their entitlement has grown from 20 days to 25. Repeat the submit-and-cancel cycle and the
balance grows without bound. Nothing in the system reports the anomaly, and nothing
self-corrects; the corrupted row stays wrong until someone edits the database.

Note the gap between fault and failure. The faulty line executes on *every* cancellation,
including the correct `Approved → Cancelled` path, where it does exactly the right thing
and the system behaves perfectly (test `ST-R06` confirms this and passes). The fault only
becomes a failure when the cancellation starts from `Requested`. **Executing the faulty
code is not enough — you have to execute it in the state that exposes it.** That single
sentence is the reason the pre-existing suite, with 95% coverage, saw nothing.

## 3. Verification or validation?

**DEF-001 was caught by verification.**

| | Question it asks | Applied here |
|---|---|---|
| **Verification** | *Are we building the product right?* Does the software conform to its specified requirements and design? | The specification says balance is deducted on approval (BR-8) and the state machine says cancellation can start from two different states (BR-7). Reading those two together tells you cancellation from `Requested` must not restore. Test `ST-R12` asserts exactly that. |
| **Validation** | *Are we building the right product?* Does the software meet the user's actual needs? | Not what found this. |

The defect surfaced during **state transition test design**, a verification activity. I was
working from `LeaveRequest.VALID_TRANSITIONS` — an internal design artefact, not a user
story — enumerating the five permitted transitions and asking of each: *what must be true
about the balance after this one?* Comparing the answer for `Requested → Cancelled` against
what the code does exposed the discrepancy before a line of test code was written. The
automated test then confirmed the failure empirically.

**Validation would probably have missed it, and this is the interesting part.** Picture the
UAT scenario: an employee submits leave, changes their mind, cancels, and checks their
balance. They see 25 days where they expected 20. Would they raise a defect? Almost
certainly not — they would assume they had miscounted, or say nothing at all, because the
system erred in their favour. There is no dissatisfied user here to drive the finding. The
only reason this defect was caught is that someone compared the behaviour to a specification
rather than to an expectation. That is the whole argument for verification existing as a
separate activity: **some defects have no unhappy user.**

The same is true of DEF-002, where the beneficiary is again the employee, and it is *not*
true of DEF-004, where an eligible employee is wrongly refused leave — that one has an
obvious complainant and validation would have found it quickly.

## 4. What I take from this

1. **Design tests from the state machine, not from the operations.** The handler was written
   against the event "cancel". The defect lives in the distinction between two transitions
   that share that event. No amount of testing "cancel works" would find it; enumerating
   ordered state pairs found it immediately.
2. **A condition that cannot be false is not a condition.** Line 97 reads like a safety
   check and is a tautology. Whenever a guard tests state that the line above just set,
   that guard is decorative. Coverage flags this as an uncoverable branch — worth treating
   as a signal, not noise.
3. **Coverage is necessary and not sufficient.** `app/routes.py` stood at 92% statement
   coverage with the fault fully executed by the existing tests. Coverage counts lines
   reached, not states reached. All five defects in this project lived in combinations and
   sequences, which is precisely what coverage does not measure.
4. **Test against the specification, not against your expectations.** The specification was
   unambiguous when its two halves — the deduction rule and the transition map — were read
   together. Nobody had read them together, and that reading is what verification is.
5. **Defects that favour the user are the ones testing has to find,** because nobody else
   will report them.

---

## References

- `defect_log.csv` — DEF-001 through DEF-005
- `docs/test_design.md` §5 — state transition design, cases ST-V01–ST-R14
- `tests/test_state_transitions.py` — automated reproducer `ST-R12`
- `app/routes.py:82-104` — `cancel_request`, the location of the fault
- `app/models.py:63-69, 138-152` — `VALID_TRANSITIONS` and the transition guard
