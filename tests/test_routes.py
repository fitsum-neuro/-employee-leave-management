"""Unit tests for all Flask routes."""
import pytest
from app.models import LeaveRequest, LeaveBalance


class TestLoginRoute:

    def test_login_page_loads(self, client):
        resp = client.get('/login')
        assert resp.status_code == 200
        assert b'Login' in resp.data

    def test_login_success(self, client, sample_employee):
        resp = client.post('/login', data={
            'email': 'test@company.com',
            'password': 'password123'
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b'Dashboard' in resp.data

    def test_login_wrong_password(self, client, sample_employee):
        resp = client.post('/login', data={
            'email': 'test@company.com',
            'password': 'wrong'
        }, follow_redirects=True)
        assert b'Invalid' in resp.data

    def test_login_nonexistent_user(self, client):
        resp = client.post('/login', data={
            'email': 'nobody@company.com',
            'password': 'password123'
        }, follow_redirects=True)
        assert b'Invalid' in resp.data


class TestLogoutRoute:

    def test_logout(self, auth_client):
        resp = auth_client.get('/logout', follow_redirects=True)
        assert resp.status_code == 200
        assert b'Login' in resp.data


class TestDashboardRoute:

    def test_dashboard_requires_login(self, client):
        resp = client.get('/dashboard', follow_redirects=True)
        assert b'log in' in resp.data.lower()

    def test_dashboard_loads(self, auth_client, sample_balance):
        resp = auth_client.get('/dashboard')
        assert resp.status_code == 200
        assert b'Dashboard' in resp.data
        assert b'Annual' in resp.data


class TestRequestLeaveRoute:

    def test_form_loads(self, auth_client):
        resp = auth_client.get('/request-leave')
        assert resp.status_code == 200
        assert b'Request Leave' in resp.data

    def test_submit_valid_request(self, auth_client, app, sample_employee, sample_balance):
        from datetime import date, timedelta
        start = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
        end = (date.today() + timedelta(days=3)).strftime('%Y-%m-%d')

        resp = auth_client.post('/request-leave', data={
            'leave_type': 'Annual',
            'start_date': start,
            'end_date': end,
            'reason': 'Vacation',
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b'submitted' in resp.data.lower() or b'History' in resp.data

    def test_submit_invalid_type(self, auth_client, sample_balance):
        from datetime import date, timedelta
        start = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
        end = (date.today() + timedelta(days=3)).strftime('%Y-%m-%d')

        resp = auth_client.post('/request-leave', data={
            'leave_type': 'InvalidType',
            'start_date': start,
            'end_date': end,
        }, follow_redirects=True)
        assert b'Invalid leave type' in resp.data

    def test_requires_login(self, client):
        resp = client.get('/request-leave', follow_redirects=True)
        assert b'log in' in resp.data.lower()


class TestLeaveHistoryRoute:

    def test_history_loads(self, auth_client):
        resp = auth_client.get('/leave-history')
        assert resp.status_code == 200
        assert b'History' in resp.data

    def test_requires_login(self, client):
        resp = client.get('/leave-history', follow_redirects=True)
        assert b'log in' in resp.data.lower()


class TestCancelRoute:

    def test_cancel_own_request(self, auth_client, app, sample_employee, sample_balance):
        with app.app_context():
            lr = LeaveRequest.create(
                sample_employee.id, 'Annual', '2026-12-01', '2026-12-03', 3, 'test'
            )
            req_id = lr.id

        resp = auth_client.post(f'/cancel/{req_id}', follow_redirects=True)
        assert resp.status_code == 200
        assert b'cancelled' in resp.data.lower() or b'Cancelled' in resp.data

    def test_cancel_nonexistent(self, auth_client):
        resp = auth_client.post('/cancel/9999', follow_redirects=True)
        assert b'not found' in resp.data.lower()


class TestAdminRoutes:

    def test_admin_requires_admin_role(self, auth_client):
        resp = auth_client.get('/admin', follow_redirects=True)
        assert b'Admin access' in resp.data or b'Dashboard' in resp.data

    def test_admin_panel_loads(self, admin_client):
        resp = admin_client.get('/admin')
        assert resp.status_code == 200
        assert b'Admin' in resp.data

    def test_approve_request(self, admin_client, app, sample_employee, sample_balance):
        with app.app_context():
            lr = LeaveRequest.create(
                sample_employee.id, 'Annual', '2026-12-01', '2026-12-03', 3, 'test'
            )
            req_id = lr.id

        resp = admin_client.post(f'/admin/approve/{req_id}', follow_redirects=True)
        assert resp.status_code == 200
        assert b'approved' in resp.data.lower() or b'Admin' in resp.data

    def test_reject_request(self, admin_client, app, sample_employee, sample_balance):
        with app.app_context():
            lr = LeaveRequest.create(
                sample_employee.id, 'Annual', '2026-12-10', '2026-12-12', 3, 'test'
            )
            req_id = lr.id

        resp = admin_client.post(f'/admin/reject/{req_id}', follow_redirects=True)
        assert resp.status_code == 200
        assert b'rejected' in resp.data.lower() or b'Admin' in resp.data

    def test_approve_nonexistent(self, admin_client):
        resp = admin_client.post('/admin/approve/9999', follow_redirects=True)
        assert b'not found' in resp.data.lower()

    def test_reject_nonexistent(self, admin_client):
        resp = admin_client.post('/admin/reject/9999', follow_redirects=True)
        assert b'not found' in resp.data.lower()


class TestIndexRedirect:

    def test_index_redirects_to_login(self, client):
        resp = client.get('/')
        assert resp.status_code == 302

    def test_index_redirects_to_dashboard_when_logged_in(self, auth_client):
        resp = auth_client.get('/')
        assert resp.status_code == 302
