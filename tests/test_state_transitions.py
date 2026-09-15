"""
State transition tests for the leave request lifecycle.

Automates every ordered state pair from docs/test_design.md section 5: the five
permitted transitions (ST-Vnn), the twenty forbidden ones (ST-Inn), and the
route-level paths that prove the application drives the machine correctly and
keeps the balance consistent (ST-Rnn).

Author: Henok Zemedkun (ATE/8552/16) - Person 2, Test Architect

States    Requested (initial) | Approved | Rejected (final) | Cancelled (final) | Taken (final)
Events    approve | reject | cancel | mark taken

Tests marked `defect` reproduce a logged defect and are expected to fail against
the current build. Run `pytest -m "not defect"` to exclude them.
"""
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.auth import hash_password
from app.models import Employee, LeaveBalance, LeaveRequest


STATES = ['Requested', 'Approved', 'Rejected', 'Cancelled', 'Taken']

VALID_PAIRS = [
    ('ST-V01', 'Requested', 'Approved'),
    ('ST-V02', 'Requested', 'Rejected'),
    ('ST-V03', 'Requested', 'Cancelled'),
    ('ST-V04', 'Approved', 'Cancelled'),
    ('ST-V05', 'Approved', 'Taken'),
]

INVALID_PAIRS = [
    ('ST-I01', 'Requested', 'Requested'),
    ('ST-I02', 'Requested', 'Taken'),
    ('ST-I03', 'Approved', 'Requested'),
    ('ST-I04', 'Approved', 'Approved'),
    ('ST-I05', 'Approved', 'Rejected'),
    ('ST-I06', 'Rejected', 'Requested'),
    ('ST-I07', 'Rejected', 'Approved'),
    ('ST-I08', 'Rejected', 'Rejected'),
    ('ST-I09', 'Rejected', 'Cancelled'),
    ('ST-I10', 'Rejected', 'Taken'),
    ('ST-I11', 'Cancelled', 'Requested'),
    ('ST-I12', 'Cancelled', 'Approved'),
    ('ST-I13', 'Cancelled', 'Rejected'),
    ('ST-I14', 'Cancelled', 'Cancelled'),
    ('ST-I15', 'Cancelled', 'Taken'),
    ('ST-I16', 'Taken', 'Requested'),
    ('ST-I17', 'Taken', 'Approved'),
    ('ST-I18', 'Taken', 'Rejected'),
    ('ST-I19', 'Taken', 'Cancelled'),
    ('ST-I20', 'Taken', 'Taken'),
]

# The legal route to each state, used to arrange a request in a given state
# without writing the status column behind the state machine's back.
PATH_TO_STATE = {
    'Requested': [],
    'Approved': ['Approved'],
    'Rejected': ['Rejected'],
    'Cancelled': ['Cancelled'],
    'Taken': ['Approved', 'Taken'],
}


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def days_from_now(n):
    return (date.today() + timedelta(days=n)).strftime('%Y-%m-%d')


def make_request(employee_id, leave_type='Annual', days=5, has_document=False):
    """Create a leave request in its initial state. Requires an app context."""
    return LeaveRequest.create(
        employee_id, leave_type,
        days_from_now(10), days_from_now(10 + days - 1),
        days, 'state transition test', has_document,
    )


def make_request_in_state(employee_id, state, leave_type='Annual', days=5):
    """
    Create a leave request and advance it to `state` using only permitted
    transitions, so the arrangement itself never contradicts the machine.
    Requires an app context.
    """
    leave_req = make_request(employee_id, leave_type, days)
    for step in PATH_TO_STATE[state]:
        success, message = leave_req.update_status(step)
        assert success, f'arranging state {state} failed at {step}: {message}'
    assert leave_req.status == state
    return leave_req


def login(app, email, password):
    """A fresh test client logged in as the given user."""
    client = app.test_client()
    client.post('/login', data={'email': email, 'password': password})
    return client


# ==========================================================================
# ST-V01 .. ST-V05  valid transitions
# ==========================================================================

class TestValidTransitions:

    @pytest.mark.parametrize(
        'case_id,from_state,to_state', VALID_PAIRS,
        ids=[f'{c}_{f}_to_{t}' for c, f, t in VALID_PAIRS],
    )
    def test_permitted_transition_is_accepted_and_persisted(
        self, app, sample_employee, sample_balance, case_id, from_state, to_state
    ):
        """Each permitted transition succeeds and is written to the database."""
        with app.app_context():
            leave_req = make_request_in_state(sample_employee.id, from_state)

            assert leave_req.can_transition_to(to_state) is True, (
                f'{case_id}: {from_state} -> {to_state} should be permitted'
            )

            success, message = leave_req.update_status(to_state)
            assert success is True, f'{case_id}: {message}'
            assert message == 'Status updated'
            assert leave_req.status == to_state

            reloaded = LeaveRequest.get_by_id(leave_req.id)
            assert reloaded.status == to_state, (
                f'{case_id}: the new state was not persisted'
            )

    def test_st_v01_approval_records_the_reviewer(
        self, app, sample_employee, sample_admin, sample_balance
    ):
        """ST-V01: approving stamps the reviewing administrator and a timestamp."""
        with app.app_context():
            leave_req = make_request(sample_employee.id)
            success, _ = leave_req.update_status('Approved', sample_admin.id)
            assert success is True

            reloaded = LeaveRequest.get_by_id(leave_req.id)
            assert reloaded.status == 'Approved'
            assert reloaded.reviewed_by == sample_admin.id
            assert reloaded.reviewed_at is not None

    def test_st_v05_taken_is_reachable_from_approved_in_the_model(
        self, app, sample_employee, sample_balance
    ):
        """
        ST-V05: the model permits Approved -> Taken. Nothing in the application
        ever performs it, which is covered separately by ST-R14 / DEF-005.
        """
        with app.app_context():
            leave_req = make_request_in_state(sample_employee.id, 'Approved')
            success, message = leave_req.update_status('Taken')
            assert (success, message) == (True, 'Status updated')
            assert LeaveRequest.get_by_id(leave_req.id).status == 'Taken'


# ==========================================================================
# ST-I01 .. ST-I20  invalid transitions
# ==========================================================================

class TestInvalidTransitions:

    @pytest.mark.parametrize(
        'case_id,from_state,to_state', INVALID_PAIRS,
        ids=[f'{c}_{f}_to_{t}' for c, f, t in INVALID_PAIRS],
    )
    def test_forbidden_transition_is_refused_and_state_is_unchanged(
        self, app, sample_employee, sample_balance, case_id, from_state, to_state
    ):
        """
        Each forbidden transition is refused with a specific message, leaves the
        in-memory object untouched, and leaves the stored row untouched.
        """
        with app.app_context():
            leave_req = make_request_in_state(sample_employee.id, from_state)

            assert leave_req.can_transition_to(to_state) is False, (
                f'{case_id}: {from_state} -> {to_state} should be forbidden'
            )

            success, message = leave_req.update_status(to_state)
            assert success is False, (
                f'{case_id}: {from_state} -> {to_state} was wrongly accepted'
            )
            assert message == f'Cannot transition from {from_state} to {to_state}'
            assert leave_req.status == from_state

            reloaded = LeaveRequest.get_by_id(leave_req.id)
            assert reloaded.status == from_state, (
                f'{case_id}: the stored state changed despite the refusal'
            )

    @pytest.mark.parametrize('state', ['Rejected', 'Cancelled', 'Taken'])
    def test_terminal_states_have_no_outgoing_transitions(
        self, app, sample_employee, sample_balance, state
    ):
        """ST-I06..I20: every target is refused from each of the three final states."""
        with app.app_context():
            for target in STATES:
                leave_req = make_request_in_state(sample_employee.id, state)
                success, _ = leave_req.update_status(target)
                assert success is False, (
                    f'{state} is terminal but accepted a move to {target}'
                )
            assert LeaveRequest.VALID_TRANSITIONS[state] == []

    def test_st_i07_rejected_can_never_become_approved(
        self, app, sample_employee, sample_balance
    ):
        """
        ST-I07: the highest-impact forbidden transition gets its own case.
        A refused request must not be quietly approved and must not move the balance.
        """
        with app.app_context():
            leave_req = make_request_in_state(sample_employee.id, 'Rejected')
            used_before = LeaveBalance.get_balance(
                sample_employee.id, 'Annual'
            ).used_days

            success, message = leave_req.update_status('Approved')

            assert success is False
            assert message == 'Cannot transition from Rejected to Approved'
            assert LeaveRequest.get_by_id(leave_req.id).status == 'Rejected'
            assert LeaveBalance.get_balance(
                sample_employee.id, 'Annual'
            ).used_days == used_before


# ==========================================================================
# ST-R01 .. ST-R11  route-level and path cases
# ==========================================================================

class TestTransitionsThroughRoutes:

    def test_st_r01_approve_route_persists_the_transition(
        self, app, sample_employee, sample_admin, sample_balance
    ):
        with app.app_context():
            request_id = make_request(sample_employee.id).id

        admin = login(app, 'admin@company.com', 'admin123')
        response = admin.post(f'/admin/approve/{request_id}')

        assert response.status_code == 302
        with app.app_context():
            reloaded = LeaveRequest.get_by_id(request_id)
            assert reloaded.status == 'Approved'
            assert reloaded.reviewed_by == sample_admin.id

    def test_st_r02_reject_route_persists_the_transition_and_moves_no_balance(
        self, app, sample_employee, sample_admin, sample_balance
    ):
        with app.app_context():
            request_id = make_request(sample_employee.id).id

        admin = login(app, 'admin@company.com', 'admin123')
        admin.post(f'/admin/reject/{request_id}')

        with app.app_context():
            assert LeaveRequest.get_by_id(request_id).status == 'Rejected'
            balance = LeaveBalance.get_balance(sample_employee.id, 'Annual')
            assert balance.used_days == 0
            assert balance.remaining_days == 20

    def test_st_r03_cancel_route_persists_the_transition(
        self, app, sample_employee, sample_balance
    ):
        with app.app_context():
            request_id = make_request(sample_employee.id).id

        employee = login(app, 'test@company.com', 'password123')
        employee.post(f'/cancel/{request_id}')

        with app.app_context():
            assert LeaveRequest.get_by_id(request_id).status == 'Cancelled'

    def test_st_r04_approval_deducts_exactly_the_requested_days(
        self, app, sample_employee, sample_admin, sample_balance
    ):
        with app.app_context():
            request_id = make_request(sample_employee.id, days=5).id

        admin = login(app, 'admin@company.com', 'admin123')
        admin.post(f'/admin/approve/{request_id}')

        with app.app_context():
            balance = LeaveBalance.get_balance(sample_employee.id, 'Annual')
            assert balance.used_days == 5
            assert balance.remaining_days == 15

    def test_st_r06_cancelling_approved_leave_restores_the_days_once(
        self, app, sample_employee, sample_admin, sample_balance
    ):
        """ST-R06: the full path Requested -> Approved -> Cancelled nets to zero."""
        with app.app_context():
            request_id = make_request(sample_employee.id, days=5).id

        admin = login(app, 'admin@company.com', 'admin123')
        admin.post(f'/admin/approve/{request_id}')
        with app.app_context():
            assert LeaveBalance.get_balance(
                sample_employee.id, 'Annual'
            ).used_days == 5

        employee = login(app, 'test@company.com', 'password123')
        employee.post(f'/cancel/{request_id}')

        with app.app_context():
            assert LeaveRequest.get_by_id(request_id).status == 'Cancelled'
            balance = LeaveBalance.get_balance(sample_employee.id, 'Annual')
            assert balance.used_days == 0, 'the days were restored more than once'
            assert balance.remaining_days == 20

    def test_st_r07_double_approval_is_refused_and_deducts_only_once(
        self, app, sample_employee, sample_admin, sample_balance
    ):
        with app.app_context():
            request_id = make_request(sample_employee.id, days=5).id

        admin = login(app, 'admin@company.com', 'admin123')
        admin.post(f'/admin/approve/{request_id}')
        admin.post(f'/admin/approve/{request_id}')

        with app.app_context():
            assert LeaveRequest.get_by_id(request_id).status == 'Approved'
            balance = LeaveBalance.get_balance(sample_employee.id, 'Annual')
            assert balance.used_days == 5, 'the balance was deducted twice'

    def test_st_r08_rejected_request_cannot_be_approved_through_the_route(
        self, app, sample_employee, sample_admin, sample_balance
    ):
        with app.app_context():
            request_id = make_request(sample_employee.id, days=5).id

        admin = login(app, 'admin@company.com', 'admin123')
        admin.post(f'/admin/reject/{request_id}')
        admin.post(f'/admin/approve/{request_id}')

        with app.app_context():
            assert LeaveRequest.get_by_id(request_id).status == 'Rejected'
            assert LeaveBalance.get_balance(
                sample_employee.id, 'Annual'
            ).used_days == 0

    def test_st_r09_an_employee_cannot_cancel_another_employees_request(
        self, app, sample_employee, sample_balance
    ):
        with app.app_context():
            Employee.create(
                employee_id='EMP002', name='Other Employee',
                email='other@company.com',
                password_hash=hash_password('password123'),
                department='Engineering', hire_date='2025-01-01',
                role='employee',
            )
            request_id = make_request(sample_employee.id).id

        intruder = login(app, 'other@company.com', 'password123')
        response = intruder.post(f'/cancel/{request_id}', follow_redirects=True)

        assert b'Unauthorized action.' in response.data
        with app.app_context():
            assert LeaveRequest.get_by_id(request_id).status == 'Requested'

    def test_st_r10_acting_on_a_missing_request_is_handled(
        self, app, sample_employee, sample_admin, sample_balance
    ):
        employee = login(app, 'test@company.com', 'password123')
        employee_response = employee.post('/cancel/99999', follow_redirects=True)
        assert employee_response.status_code == 200
        assert b'Leave request not found.' in employee_response.data

        admin = login(app, 'admin@company.com', 'admin123')
        for route in ('/admin/approve/99999', '/admin/reject/99999'):
            admin_response = admin.post(route, follow_redirects=True)
            assert admin_response.status_code == 200
            assert b'Leave request not found.' in admin_response.data

    def test_st_r11_guard_and_updater_agree_on_all_25_pairs(
        self, app, sample_employee, sample_balance
    ):
        """
        ST-R11: can_transition_to must be a faithful guard - for every ordered
        pair its verdict matches what update_status actually does, so the guard
        can neither be bypassed nor block a permitted move.
        """
        expected = {(f, t) for _, f, t in VALID_PAIRS}

        with app.app_context():
            for from_state in STATES:
                for to_state in STATES:
                    leave_req = make_request_in_state(
                        sample_employee.id, from_state
                    )
                    guard = leave_req.can_transition_to(to_state)
                    success, _ = leave_req.update_status(to_state)

                    assert guard == success, (
                        f'{from_state} -> {to_state}: can_transition_to said '
                        f'{guard} but update_status returned {success}'
                    )
                    assert success == ((from_state, to_state) in expected), (
                        f'{from_state} -> {to_state} disagrees with the '
                        f'state transition table in the Test Design Document'
                    )


# ==========================================================================
# Defect probes - expected to fail against the current build
# ==========================================================================

class TestStateTransitionDefectProbes:

    @pytest.mark.defect
    def test_st_r12_cancelling_a_requested_leave_must_not_credit_the_balance(
        self, app, sample_employee, sample_balance
    ):
        """
        ST-R12 (DEF-001).

        Balance is deducted on approval, never on submission. cancel_request in
        routes.py:95-99 nevertheless restores unconditionally after any
        successful move to Cancelled, so cancelling a request that was still
        Requested credits days that were never taken. used_days goes negative
        and the employee gains free leave, repeatably.
        """
        with app.app_context():
            request_id = make_request(sample_employee.id, days=5).id
            before = LeaveBalance.get_balance(sample_employee.id, 'Annual')
            assert before.used_days == 0
            assert before.remaining_days == 20

        employee = login(app, 'test@company.com', 'password123')
        employee.post(f'/cancel/{request_id}')

        with app.app_context():
            assert LeaveRequest.get_by_id(request_id).status == 'Cancelled'
            after = LeaveBalance.get_balance(sample_employee.id, 'Annual')
            assert after.used_days == 0, (
                f'DEF-001: cancelling a never-approved request set used_days to '
                f'{after.used_days}; no deduction had been made, so none was due back'
            )
            assert after.remaining_days == 20, (
                f'DEF-001: balance inflated to {after.remaining_days} days'
            )

    @pytest.mark.defect
    def test_st_r13_approval_must_re_check_the_balance(
        self, app, sample_employee, sample_admin, sample_balance
    ):
        """
        ST-R13 (DEF-002).

        Eligibility is checked only at submission, when nothing has been deducted
        yet, and approve_request in routes.py:123-126 deducts without re-checking.
        Two 20-day requests against a 20-day balance therefore both pass
        eligibility and both get approved, granting double the entitlement.
        """
        with app.app_context():
            first_id = make_request(sample_employee.id, days=20).id
            second_id = make_request(sample_employee.id, days=20).id

        admin = login(app, 'admin@company.com', 'admin123')
        admin.post(f'/admin/approve/{first_id}')
        admin.post(f'/admin/approve/{second_id}')

        with app.app_context():
            balance = LeaveBalance.get_balance(sample_employee.id, 'Annual')
            second = LeaveRequest.get_by_id(second_id)

            assert balance.used_days <= balance.total_days, (
                f'DEF-002: used_days {balance.used_days} exceeds the '
                f'{balance.total_days}-day entitlement'
            )
            assert balance.remaining_days >= 0, (
                f'DEF-002: remaining_days went to {balance.remaining_days}'
            )
            assert second.status == 'Requested', (
                'DEF-002: the second request was approved although the balance '
                'could no longer cover it'
            )

    @pytest.mark.defect
    def test_st_r14_taken_state_is_reachable_from_the_application(self):
        """
        ST-R14 (DEF-005).

        models.py declares Approved -> Taken, but no route, admin action,
        scheduled job or template anywhere in app/ ever sets the status to
        'Taken'. A documented terminal state is unreachable in the running
        system, so approved leave can never be marked as consumed.
        """
        app_dir = Path(__file__).resolve().parent.parent / 'app'
        sources = [
            path for path in app_dir.rglob('*')
            if path.suffix in {'.py', '.html'} and path.name != 'models.py'
        ]
        callers = [
            f'{path.relative_to(app_dir)}:{number}'
            for path in sources
            for number, line in enumerate(
                path.read_text(encoding='utf-8').splitlines(), start=1
            )
            if 'Taken' in line
        ]

        assert callers, (
            "DEF-005: nothing outside app/models.py ever references the 'Taken' "
            'state, so the Approved -> Taken transition declared in '
            'LeaveRequest.VALID_TRANSITIONS can never be triggered'
        )
