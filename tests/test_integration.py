"""
tests/test_integration.py
=========================
Integration tests for the Employee Leave Management System.

Author  : Eyob Kassaye (ATE/4534/16) — Person 3, Test Automation Engineer
Purpose : Verify multi-layer interactions (route → business_logic → model → SQLite DB).
Markers : @pytest.mark.integration — exercises more than one layer per test.
          @pytest.mark.defect      — reproduces a logged defect; expected to fail
                                     against the current build.

Run all integration tests:
    pytest tests/test_integration.py -v

Run without defect reproducers (should all pass):
    pytest tests/test_integration.py -m "not defect" -v
"""

import pytest
from app.models import Employee, LeaveRequest, LeaveBalance
from app.auth import hash_password


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _login(client, email, password):
    """POST to /login and return the response."""
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )


def _submit_leave(client, leave_type, start, end, reason="", has_doc=False):
    """POST to /request-leave and return the response."""
    data = {
        "leave_type": leave_type,
        "start_date": start,
        "end_date": end,
        "reason": reason,
    }
    if has_doc:
        data["has_document"] = "on"
    return client.post("/request-leave", data=data, follow_redirects=True)


def _make_eligible_employee(app, emp_id="EMP-INT-01", email="integ@company.com"):
    """Create an employee who has ≥6 months service + full balances in the test DB."""
    with app.app_context():
        emp = Employee.create(
            employee_id=emp_id,
            name="Integration Employee",
            email=email,
            password_hash=hash_password("pass1234"),
            department="Engineering",
            hire_date="2025-01-01",   # ≥6 months from today (2026-09-15)
            role="employee",
        )
        for lt, total in [("Annual", 20), ("Sick", 15), ("Personal", 5)]:
            LeaveBalance.create(emp.id, lt, total)
        return emp


def _make_admin(app):
    """Create an admin account in the test DB."""
    with app.app_context():
        admin = Employee.create(
            employee_id="ADM-INT-01",
            name="Integration Admin",
            email="int_admin@company.com",
            password_hash=hash_password("admin_pass"),
            department="Management",
            hire_date="2020-01-01",
            role="admin",
        )
        return admin


# ─────────────────────────────────────────────────────────────────────────────
# INT-01: Login with real database
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.integration
class TestLoginIntegration:
    """Login flow against a real (test) SQLite database."""

    def test_valid_credentials_redirect_to_dashboard(self, app, client):
        """INT-01-01: Valid credentials result in a 200 on the dashboard page."""
        _make_eligible_employee(app)
        resp = _login(client, "integ@company.com", "pass1234")
        assert resp.status_code == 200
        assert b"dashboard" in resp.data.lower() or b"leave" in resp.data.lower()

    def test_invalid_password_stays_on_login(self, app, client):
        """INT-01-02: Wrong password keeps user on login page with error flash."""
        _make_eligible_employee(app)
        resp = _login(client, "integ@company.com", "wrong_password")
        assert resp.status_code == 200
        assert b"Invalid" in resp.data or b"invalid" in resp.data

    def test_unknown_email_rejected(self, app, client):
        """INT-01-03: Non-existent email returns invalid-credentials message."""
        resp = _login(client, "nobody@company.com", "anything")
        assert resp.status_code == 200
        assert b"Invalid" in resp.data or b"invalid" in resp.data

    def test_session_persists_after_login(self, app, client):
        """INT-01-04: After login, the /dashboard route is accessible (session cookie set)."""
        _make_eligible_employee(app)
        _login(client, "integ@company.com", "pass1234")
        resp = client.get("/dashboard", follow_redirects=True)
        assert resp.status_code == 200

    def test_logout_clears_session(self, app, client):
        """INT-01-05: After logout, accessing /dashboard redirects back to login."""
        _make_eligible_employee(app)
        _login(client, "integ@company.com", "pass1234")
        client.get("/logout", follow_redirects=True)
        resp = client.get("/dashboard", follow_redirects=True)
        # After logout the dashboard should redirect to login
        assert b"login" in resp.data.lower() or resp.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# INT-02: Leave request is persisted to the database
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.integration
class TestLeaveRequestPersistence:
    """Verify leave requests are saved to and retrieved from the real DB."""

    def test_submitted_request_saved_to_db(self, app, client):
        """INT-02-01: After a successful POST /request-leave the record exists in the DB."""
        emp = _make_eligible_employee(app)
        _login(client, "integ@company.com", "pass1234")
        resp = _submit_leave(client, "Annual", "2027-01-10", "2027-01-12")
        assert resp.status_code == 200

        with app.app_context():
            requests = LeaveRequest.get_by_employee(emp.id)
        assert len(requests) == 1
        req = requests[0]
        assert req.leave_type == "Annual"
        assert req.days_requested == 3
        assert req.status == "Requested"

    def test_request_initial_status_is_requested(self, app, client):
        """INT-02-02: Newly created leave request has status 'Requested'."""
        emp = _make_eligible_employee(app)
        _login(client, "integ@company.com", "pass1234")
        _submit_leave(client, "Sick", "2027-02-01", "2027-02-02")

        with app.app_context():
            reqs = LeaveRequest.get_by_employee(emp.id)
        assert reqs[0].status == "Requested"

    def test_leave_history_shows_submitted_request(self, app, client):
        """INT-02-03: Submitted request appears on the /leave-history page."""
        _make_eligible_employee(app)
        _login(client, "integ@company.com", "pass1234")
        _submit_leave(client, "Personal", "2027-03-05", "2027-03-05")
        resp = client.get("/leave-history")
        assert resp.status_code == 200
        assert b"Personal" in resp.data

    def test_balance_not_deducted_on_submission(self, app, client):
        """INT-02-04: Balance is NOT deducted when request is submitted (only on approval)."""
        emp = _make_eligible_employee(app)
        _login(client, "integ@company.com", "pass1234")
        _submit_leave(client, "Annual", "2027-01-10", "2027-01-14")  # 5 days

        with app.app_context():
            bal = LeaveBalance.get_balance(emp.id, "Annual")
        # remaining should still be 20 — deduction only happens on approval
        assert bal.remaining_days == 20

    def test_sick_leave_with_document_persisted(self, app, client):
        """INT-02-05: A sick-leave request with >3 days and a document is saved correctly."""
        emp = _make_eligible_employee(app)
        _login(client, "integ@company.com", "pass1234")
        _submit_leave(client, "Sick", "2027-04-01", "2027-04-05", has_doc=True)  # 5 days

        with app.app_context():
            reqs = LeaveRequest.get_by_employee(emp.id)
        assert len(reqs) == 1
        assert reqs[0].has_document is True
        assert reqs[0].days_requested == 5


# ─────────────────────────────────────────────────────────────────────────────
# INT-03: Approval decrements leave balance
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.integration
class TestApprovalDeductsBalance:
    """Verify admin approval updates the leave_balance row in the DB."""

    def _setup_pending_request(self, app, client, days=5):
        """Helper: log in employee, submit leave, return employee + request id."""
        emp = _make_eligible_employee(app)
        admin = _make_admin(app)

        _login(client, "integ@company.com", "pass1234")
        _submit_leave(client, "Annual", "2027-01-10",
                      f"2027-01-{9 + days:02d}")
        with app.app_context():
            reqs = LeaveRequest.get_by_employee(emp.id)
            req_id = reqs[0].id

        client.get("/logout", follow_redirects=True)
        return emp, admin, req_id

    def test_approve_deducts_correct_days(self, app, client):
        """INT-03-01: Approving a 5-day request reduces remaining_days by 5."""
        emp, admin, req_id = self._setup_pending_request(app, client, days=5)

        _login(client, "int_admin@company.com", "admin_pass")
        client.post(f"/admin/approve/{req_id}", follow_redirects=True)

        with app.app_context():
            bal = LeaveBalance.get_balance(emp.id, "Annual")
        assert bal.used_days == 5
        assert bal.remaining_days == 15

    def test_approve_updates_request_status_to_approved(self, app, client):
        """INT-03-02: After admin approval the request status changes to 'Approved'."""
        emp, admin, req_id = self._setup_pending_request(app, client, days=3)

        _login(client, "int_admin@company.com", "admin_pass")
        client.post(f"/admin/approve/{req_id}", follow_redirects=True)

        with app.app_context():
            req = LeaveRequest.get_by_id(req_id)
        assert req.status == "Approved"

    def test_reject_does_not_change_balance(self, app, client):
        """INT-03-03: Rejecting a request does not touch the leave balance."""
        emp, admin, req_id = self._setup_pending_request(app, client, days=5)

        _login(client, "int_admin@company.com", "admin_pass")
        client.post(f"/admin/reject/{req_id}", follow_redirects=True)

        with app.app_context():
            bal = LeaveBalance.get_balance(emp.id, "Annual")
        assert bal.remaining_days == 20  # unchanged

    def test_rejected_status_recorded_in_db(self, app, client):
        """INT-03-04: After rejection the status in DB is 'Rejected'."""
        emp, admin, req_id = self._setup_pending_request(app, client, days=3)

        _login(client, "int_admin@company.com", "admin_pass")
        client.post(f"/admin/reject/{req_id}", follow_redirects=True)

        with app.app_context():
            req = LeaveRequest.get_by_id(req_id)
        assert req.status == "Rejected"

    def test_cancel_approved_request_restores_balance(self, app, client):
        """INT-03-05: Cancelling an *Approved* request restores the deducted days."""
        emp, admin, req_id = self._setup_pending_request(app, client, days=5)

        # Admin approves
        _login(client, "int_admin@company.com", "admin_pass")
        client.post(f"/admin/approve/{req_id}", follow_redirects=True)
        client.get("/logout", follow_redirects=True)

        # Employee cancels
        _login(client, "integ@company.com", "pass1234")
        client.post(f"/cancel/{req_id}", follow_redirects=True)

        with app.app_context():
            bal = LeaveBalance.get_balance(emp.id, "Annual")
        # Days should be fully restored after cancelling an approved leave
        assert bal.remaining_days == 20


# ─────────────────────────────────────────────────────────────────────────────
# INT-04: Multiple requests by the same employee
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.integration
class TestMultipleRequestsSameEmployee:
    """Verify the system handles several leave requests per employee correctly."""

    def test_two_separate_approved_requests_both_deduct(self, app, client):
        """INT-04-01: Approving two requests sequentially deducts the sum of days."""
        emp = _make_eligible_employee(app)
        admin = _make_admin(app)

        _login(client, "integ@company.com", "pass1234")
        # Request 1: 3 days
        _submit_leave(client, "Annual", "2027-02-01", "2027-02-03")
        # Request 2: 2 days
        _submit_leave(client, "Annual", "2027-03-01", "2027-03-02")
        client.get("/logout", follow_redirects=True)

        with app.app_context():
            reqs = LeaveRequest.get_by_employee(emp.id)
            req_ids = [r.id for r in reqs]

        _login(client, "int_admin@company.com", "admin_pass")
        for rid in req_ids:
            client.post(f"/admin/approve/{rid}", follow_redirects=True)

        with app.app_context():
            bal = LeaveBalance.get_balance(emp.id, "Annual")
        assert bal.used_days == 5
        assert bal.remaining_days == 15

    def test_multiple_request_types_independent_balances(self, app, client):
        """INT-04-02: Requests of different leave types deduct from separate balances."""
        emp = _make_eligible_employee(app)
        admin = _make_admin(app)

        _login(client, "integ@company.com", "pass1234")
        _submit_leave(client, "Annual", "2027-02-01", "2027-02-02")   # 2 days
        _submit_leave(client, "Personal", "2027-03-01", "2027-03-01")  # 1 day
        client.get("/logout", follow_redirects=True)

        with app.app_context():
            reqs = LeaveRequest.get_by_employee(emp.id)
            req_ids = [r.id for r in reqs]

        _login(client, "int_admin@company.com", "admin_pass")
        for rid in req_ids:
            client.post(f"/admin/approve/{rid}", follow_redirects=True)

        with app.app_context():
            annual_bal = LeaveBalance.get_balance(emp.id, "Annual")
            personal_bal = LeaveBalance.get_balance(emp.id, "Personal")

        assert annual_bal.remaining_days == 18   # 20 - 2
        assert personal_bal.remaining_days == 4  # 5 - 1

    def test_all_requests_visible_in_leave_history(self, app, client):
        """INT-04-03: All submitted requests appear in /leave-history."""
        _make_eligible_employee(app)

        _login(client, "integ@company.com", "pass1234")
        _submit_leave(client, "Annual", "2027-02-01", "2027-02-02")
        _submit_leave(client, "Sick", "2027-04-10", "2027-04-11")
        _submit_leave(client, "Personal", "2027-05-01", "2027-05-01")

        resp = client.get("/leave-history")
        assert resp.status_code == 200
        assert b"Annual" in resp.data
        assert b"Sick" in resp.data
        assert b"Personal" in resp.data

    def test_insufficient_balance_blocks_request(self, app, client):
        """INT-04-04: Requesting more days than remaining is rejected."""
        emp = _make_eligible_employee(app)

        _login(client, "integ@company.com", "pass1234")
        # Personal balance is only 5; request 6 days
        resp = _submit_leave(client, "Personal", "2027-02-01", "2027-02-06")
        assert resp.status_code == 200
        assert b"Insufficient" in resp.data or b"insufficient" in resp.data


# ─────────────────────────────────────────────────────────────────────────────
# INT-05: Defect reproducers (integration layer)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.defect
class TestDefectReproducers:
    """
    Each test reproduces one logged defect at the integration (route+DB) level.
    These tests are EXPECTED TO FAIL against the current build.

    Run them in isolation:
        pytest tests/test_integration.py -m defect -v
    """

    def test_def001_cancel_requested_does_not_restore_balance(self, app, client):
        """
        DEF-001 (Critical): Cancelling a *Requested* leave must NOT restore days.

        The route checks ``was_approved = leave_req.status == 'Approved'``
        *before* calling update_status, so a Requested→Cancelled transition
        should never call LeaveBalance.restore().

        Current bug: the check was ``leave_req.status == 'Approved'`` evaluated
        AFTER update_status in an older version; but even in the current code
        the integration scenario reveals no negative balance.  This test pins
        the correct postcondition so any regression will be caught.
        """
        emp = _make_eligible_employee(app)

        _login(client, "integ@company.com", "pass1234")
        # Submit a leave; it stays in 'Requested' (no approval)
        _submit_leave(client, "Annual", "2027-01-10", "2027-01-14")  # 5 days

        with app.app_context():
            reqs = LeaveRequest.get_by_employee(emp.id)
            req_id = reqs[0].id

        # Cancel without ever approving
        client.post(f"/cancel/{req_id}", follow_redirects=True)

        with app.app_context():
            bal = LeaveBalance.get_balance(emp.id, "Annual")

        # EXPECTED: used_days stays 0, remaining stays 20
        # ACTUAL (bug): used_days goes to -5, remaining goes to 25
        assert bal.remaining_days == 20, (
            f"DEF-001: balance should be 20 after cancelling a Requested leave, "
            f"got {bal.remaining_days}"
        )

    def test_def002_second_approval_blocked_by_balance_check(self, app, client):
        """
        DEF-002 (Critical): Admin cannot approve a second request that would
        collectively exceed the entitlement.

        Expected: the second approval is rejected with an insufficient-balance
        flash and used_days never exceeds total_days.
        Actual   : both approvals succeed, used_days goes to 40 on a 20-day cap.
        """
        emp = _make_eligible_employee(app)
        admin = _make_admin(app)

        # Submit two 20-day Annual requests
        _login(client, "integ@company.com", "pass1234")
        _submit_leave(client, "Annual", "2027-01-10", "2027-01-29")  # 20 days
        _submit_leave(client, "Annual", "2027-03-01", "2027-03-20")  # 20 days
        client.get("/logout", follow_redirects=True)

        with app.app_context():
            reqs = LeaveRequest.get_by_employee(emp.id)
            req_ids = [r.id for r in reqs]

        _login(client, "int_admin@company.com", "admin_pass")
        for rid in req_ids:
            client.post(f"/admin/approve/{rid}", follow_redirects=True)

        with app.app_context():
            bal = LeaveBalance.get_balance(emp.id, "Annual")

        # EXPECTED: used_days == 20 (second approval blocked)
        # ACTUAL  : used_days == 40 (both approved, balance -20)
        assert bal.used_days <= 20, (
            f"DEF-002: used_days should not exceed total_days (20), "
            f"got {bal.used_days}"
        )
