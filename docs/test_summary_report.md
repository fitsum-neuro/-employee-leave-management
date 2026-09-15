# Test Summary Report — Employee Leave Management System

## Document Control

| Field | Value |
|---|---|
| Document | Test Summary Report |
| Project | Employee Leave Management System |
| Course | Software Testing & Validation — Final Project |
| Version | 1.0 |
| Date | 2026-09-15 |
| Author | Henok Zemedkun (Person 2 — Test Architect & Document Author) |
| Basis | [`test_plan.md`](test_plan.md), [`test_design.md`](test_design.md), `defect_log.csv`, `metrics.json` |

### Team Members

| Name | Student ID | Role |
|---|---|---|
| Fitsum Yoseph | ATE/5804/16 | Person 1 — Application Developer |
| Henok Zemedkun | ATE/8552/16 | Person 2 — Test Architect & Document Author |
| Eyob Kassaye | ATE/4534/16 | Person 3 — Test Automation Engineer & CI/CD |

---

## 1. Summary

116 test cases were designed from four black-box techniques and realised as 152 automated
pytest tests. All 152 executed. 147 passed. The 5 that failed are deliberate defect
reproducers, one for each of the five defects recorded in `defect_log.csv`.

Statement coverage of `app/` reached **98.37%** and branch coverage **94.87%**; the core
rule engine `app/business_logic.py` reached **100%** on both, against an 80% target.

**Nine of the ten exit criteria are met. The one that is not — zero open Critical defects —
is not met, and it is the criterion that governs release.** Two defects corrupt the leave
balance: one lets an employee mint leave days out of nothing, the other lets an
administrator grant double the annual entitlement. The recommendation below is therefore
**no-go for release** until those two are fixed and retested.

## 2. What Was Tested

| Area | Technique(s) | Cases | Outcome |
|---|---|---|---|
| Leave type validation (BR-3) | EP, decision table | EP-07–12, DT-01, DT-02 | Pass. The type list is enforced and case-sensitive; the check correctly precedes all others. |
| Day range 1–30 (BR-2) | EP, BVA, decision table | EP-01–06, BVA-01–06, BVA-26–27, DT-03–06 | Pass at every boundary (0/1/2, 29/30/31). One type-guard weakness found — DEF-003. |
| Six-month service rule (BR-1) | EP, BVA, decision table | EP-13–15, BVA-07–11, DT-07, DT-08 | Pass at 5/6/7 months. A month-end arithmetic fault found — DEF-004. |
| Balance sufficiency (BR-4) | EP, BVA, decision table | EP-16–18, BVA-16–19, DT-09, DT-10, DT-21 | Pass at unit level, including the missing-balance-record case. Fails at approval time — DEF-002. |
| Sick-leave document rule (BR-5) | EP, BVA, decision table | EP-19–21, BVA-12–15, DT-11, DT-12, DT-16–18 | Pass. The 3-versus-4-day boundary is correct, and `has_document` is properly ignored when the rule does not apply. |
| Date validation (BR-6) | EP, BVA | EP-22–26, BVA-20–25 | Pass. Malformed, past and inverted ranges are all rejected; day counting is inclusive. |
| Rule precedence | Decision table | DT-02, DT-04, DT-06, DT-08, DT-10 | Pass. The five conditions are evaluated in the documented order, so the user always sees the most relevant refusal message. |
| State machine, all 25 ordered pairs (BR-7) | State transition | ST-V01–V05, ST-I01–I20 | Pass. The 5 permitted transitions work and persist; the 20 forbidden ones are refused with a specific message and leave the stored row untouched. |
| Terminal-state property | State transition | ST-I06–I20 | Pass. `Rejected`, `Cancelled` and `Taken` accept no outgoing transition. |
| Guard consistency | State transition | ST-R11 | Pass. `can_transition_to` agrees with `update_status` on all 25 pairs, so the guard cannot be bypassed. |
| Balance arithmetic along each path (BR-8) | State transition | ST-R04–R06 | Pass on the approve and approve-then-cancel paths. Fails on the cancel-from-Requested path — DEF-001. |
| Route-level authorisation | State transition | ST-R09, ST-R10 | Pass. One employee cannot cancel another's request, and missing requests are handled without a 500. |
| Reachability of `Taken` | State transition | ST-R14 | **Fail** — DEF-005. |
| Orchestration end to end | Decision table | DT-22 | Pass. Every rule holds through `process_leave_request`, and no request object is created for a refusing rule. |

## 3. What Was Not Tested

### 3.1 Excluded by the Test Plan

These were declared out of scope in `test_plan.md` §3.2 and no cases were written for them.
Each carries residual risk, quantified in §7.

| Not tested | Reason |
|---|---|
| Performance, load, stress | No non-functional requirement stated. |
| Security penetration — SQL injection, XSS, CSRF, session fixation | Out of course scope. Note that no route carries a CSRF token, and every state-changing route is a bare `POST`. |
| Concurrency and race conditions | No locking requirement. Two administrators approving simultaneously is untested, and the read-modify-write in `LeaveBalance.deduct` is not atomic against it. |
| Cross-browser, responsive and visual rendering | Single reference browser agreed for system tests. |
| Database migration and upgrade | The schema is created once by `init_db`; no versioned migrations exist. |
| Localisation, accessibility, i18n | Not required. |

### 3.2 Gaps inside the tested scope

| Gap | Location | Assessment |
|---|---|---|
| `admin_required` when no user is logged in at all | `app/auth.py:37-38` | The wrong-role branch is covered; the not-logged-in branch of the admin decorator is not. Low risk — `login_required` covers the identical branch and passes — but it belongs in Person 3's route tests. |
| `LeaveBalance.from_row(None)` | `app/models.py:170` | The `None`-row guard is never executed, because `calculate_leave_balance` is what handles a missing balance and that path *is* covered (DT-09). Cosmetic. |
| `create_app` without a test config | `app/__init__.py:75->78` | The production configuration branch is never taken under test, by construction. Accepted. |
| `routes.py:97->100` partial branch | `app/routes.py` | **Not coverable.** The guard tests `leave_req.status == 'Cancelled'` *after* `update_status` has already set it, so the false arm is unreachable. This unreachable branch is precisely the fault behind DEF-001, and it disappears once DEF-001 is fixed. |
| Selenium system tests and UAT | `tests/` | Owned by Person 3 and the team; not executed at the time of this report. Exit criterion E7 for UAT is therefore not yet assessable. |

## 4. Results Against Exit Criteria

| # | Criterion | Target | Actual | Verdict |
|---|---|---|---|---|
| X1 | Designed cases executed | 100% | 116 of 116 designed cases, as 152 automated tests | ✅ **Met** |
| X2 | Cases passed | ≥ 95%, every failure traced to a defect | 147 of 152 = **96.71%**; all 5 failures trace to DEF-001…DEF-005 | ✅ **Met** |
| X3 | Branch coverage of `business_logic.py` | ≥ 80% | **100%** (30 of 30 branches) | ✅ **Met** |
| X4 | Statement coverage of `app/` | ≥ 85% | **98.37%** (346 of 352 statements) | ✅ **Met** |
| X5 | Critical and High defects open | 0 | **2 open** — DEF-001, DEF-002 | ❌ **Not met** |
| X6 | Medium defects open | ≤ 3, each with a workaround | 2 open — DEF-004, DEF-005, workarounds in §6 | ✅ **Met** |
| X7 | Every decision table rule automated | 100% of rules | 9 of 9 rules, each with ≥ 2 tests | ✅ **Met** |
| X8 | Every state transition automated | 25 of 25 pairs | 25 of 25 (5 valid, 20 invalid) | ✅ **Met** |
| X9 | Documentation complete and committed | All six artefacts | Plan, Design, Defect Log, Metrics, this report, Reflection | ✅ **Met** |
| X10 | CI green on the final commit, excluding defect reproducers | Pass | `pytest -m "not defect"` → 147 passed, 5 deselected | ✅ **Met** |

**9 of 10 met. X5 is not met, and X5 is the release gate.**

## 5. Quality Metrics

Measured values from `metrics.json`, regenerable with `python3 tools/collect_metrics.py`.

| Metric | Value | Basis |
|---|---|---|
| Defects found | 5 | `defect_log.csv` |
| Defects escaped to users | 0 | The system has not been released. |
| Defect density | **10.0 per KLOC** | 5 defects ÷ 500 non-blank, non-comment lines in `app/` |
| Defect removal efficiency (pre-release) | **100%** | All 5 found before release |
| Defect removal efficiency (unit test phase) | **0%** | The 52 unit tests that predated this test design passed against all 5 defects |
| Statement coverage | **98.37%** | 346 of 352 statements |
| Branch coverage | **94.87%** | 74 of 78 branches |
| `business_logic.py` coverage | **100% / 100%** | statement / branch |
| Automated tests | 152 total, 147 pass, 5 fail | All 5 failures are defect reproducers |

**The number worth arguing about is the 0% unit-phase DRE.** Fifty-two unit tests and 95%
coverage existed before this test design started, and they found none of these five defects.
Coverage measures which lines ran, not which *combinations* of conditions and which
*sequences* of states were exercised. Every one of the five defects lives in a combination
or a sequence: DEF-001 and DEF-002 need a specific ordering of state changes, DEF-005 is an
absent code path that no coverage tool can flag, and DEF-003 and DEF-004 need input values
no one thought to try. That is the practical case for decision table and state transition
testing, and it is the single most transferable finding of this project.

## 6. Outstanding Defects

All five defects are **Open**. None has been fixed; by agreement the application code
remains Person 1's to change, and this report exists to give them the evidence.

| ID | Severity | Priority | Summary | Reproducer | Workaround |
|---|---|---|---|---|---|
| DEF-001 | **Critical** | High | Cancelling a leave request still in `Requested` restores days that were never deducted. `used_days` goes to −5 and the balance inflates to 25 of 20. Repeatable without limit. | `ST-R12` — `tests/test_state_transitions.py::TestStateTransitionDefectProbes::test_st_r12_...` | None that a user can apply. An administrator must correct `used_days` in the database by hand. |
| DEF-002 | **Critical** | High | Approval never re-checks the balance. Two 20-day requests against a 20-day entitlement are both approved: `used_days` 40, `remaining_days` −20. | `ST-R13` — `...::test_st_r13_approval_must_re_check_the_balance` | Procedural only: the administrator must check the employee's remaining balance manually before each approval. |
| DEF-004 | Medium | Medium | `calculate_service_months` undercounts by one month for hire dates on the 29th–31st, so an eligible employee is refused on the last day of a short month. | `DT-20` — `tests/test_decision_table.py::...::test_dt_20_service_months_at_a_month_end_hire_date` | The employee can re-submit the following day, when the count corrects itself. |
| DEF-005 | Medium | Medium | The `Taken` state is unreachable. `Approved → Taken` is declared in the model but nothing in `app/` ever performs it. | `ST-R14` — `...::test_st_r14_taken_state_is_reachable_from_the_application` | Treat `Approved` as meaning both "upcoming" and "taken", and distinguish them by comparing the end date by eye. |
| DEF-003 | Low | Low | `check_eligibility` accepts a boolean as `days_requested` and treats `True` as a one-day request. | `DT-19` — `...::test_dt_19_boolean_day_count_is_a_wrong_type_not_one_day` | Not reachable through the web UI, where the day count is always computed as an integer. API callers must pass an `int`. |

Each reproducer asserts the **specified** behaviour, so it turns from a failure into a
passing regression test the moment the defect is fixed — no test edit required.

## 7. Residual Risk

| Risk | Exposure | Likelihood | Impact | Mitigation available now |
|---|---|---|---|---|
| **Balance corruption in production** | DEF-001 and DEF-002 both corrupt `leave_balance` and neither is self-correcting; every corrupted row stays wrong until someone edits the database. | **High** — DEF-001 triggers on an ordinary, legitimate user action (cancelling your own pending request) | **High** — direct financial and HR consequence: paid leave granted that was never earned | None. This is the reason for the no-go below. |
| Undetected historical corruption | If either defect has run against any real data, `used_days` may already be wrong and nothing reports it. | Medium | High | Before any release, audit for `used_days < 0` or `used_days > total_days`. |
| Concurrency on the balance | `LeaveBalance.deduct` and `.restore` are read-modify-write with no locking. Two simultaneous approvals could lose an update. Untested and out of scope. | Low at coursework scale | High | Not addressed. Would need a transaction or a conditional update. |
| No CSRF protection | Every state-changing route is a bare `POST` with no token, so cancel, approve and reject are forgeable from another site. Out of scope by the plan. | Medium if deployed publicly | High | Not addressed. Flask-WTF would close it. |
| `Taken` never reached | DEF-005 means reporting cannot distinguish consumed leave from approved future leave. | Certain — it is unconditional | Low to medium | Compare end dates manually. |
| Untested system and UAT levels | Selenium tests and UAT were not executed for this report. Browser-level regressions would not be caught. | Medium | Medium | Run Person 3's Selenium suite before release. |
| Month-end eligibility refusals | DEF-004 wrongly refuses a small population (hire dates on the 29th–31st) on specific days. | Low | Low | The employee re-submits the next day. |

## 8. Release Recommendation

### 🔴 NO-GO for release.

Exit criterion X5 — zero open Critical or High severity defects — is not met, and the two
defects that breach it, DEF-001 and DEF-002, both destroy the integrity of the leave
balance. Leave balance *is* the product: an employee who can cancel a pending request to
mint five days of leave, and an administrator who can approve double the annual
entitlement without being stopped, together mean the system cannot be trusted with the one
number it exists to hold. Neither defect is exotic — DEF-001 fires on an entirely ordinary
user action, and it is not self-correcting.

Every other criterion is met, and comfortably: coverage is well above target, the rule
engine is exhaustively covered, and all 25 state pairs behave exactly as specified. The
product is close. It is not ready.

**Conditions for a go decision**

1. Fix DEF-001 — restore the balance only when the previous status was `Approved`; test the
   status *before* the transition, not after.
2. Fix DEF-002 — re-check the remaining balance inside `approve_request` before deducting,
   and refuse the approval if it no longer covers the request.
3. Re-run the suite. `ST-R12` and `ST-R13` must go green with no change to the test code.
4. Audit existing data for `used_days < 0` or `used_days > total_days` and correct any rows.
5. Run the Selenium system suite and complete UAT (Test Plan entry criteria E6, E7).
6. DEF-003, DEF-004 and DEF-005 may be deferred to a follow-up release under the accepted
   residual risk in §7, provided the workarounds in §6 are communicated to users.

**Interim position.** For coursework demonstration on a throwaway database, the build is
fine to show and the defect reproducers are part of what is worth showing. That is a demo
decision, not a release decision, and it does not change the no-go above.

## 9. Conclusion

Four black-box design techniques applied to a codebase that already had 52 passing unit
tests and 95% coverage found five real defects, two of them critical. The techniques earned
their place: the decision table found what testing conditions one at a time could not, and
state transition testing found what testing single operations could not. Coverage told us
which lines had run; it could not tell us which sequences had been tried, and that gap is
where every serious defect in this project turned out to live.

---

### Sign-off

| Role | Name | Signature | Date |
|---|---|---|---|
| Test Architect | Henok Zemedkun | | |
| Application Developer | Fitsum Yoseph | | |
| Automation / CI Engineer | Eyob Kassaye | | |
