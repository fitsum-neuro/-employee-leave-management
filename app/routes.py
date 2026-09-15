from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.auth import login_user, login_required, admin_required
from app.models import Employee, LeaveRequest, LeaveBalance
from app.business_logic import process_leave_request, validate_leave_dates, calculate_leave_balance

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('main.login'))


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        employee = login_user(email, password)
        if employee:
            session['user_id'] = employee.id
            session['user_name'] = employee.name
            session['user_role'] = employee.role
            flash('Login successful.', 'success')
            return redirect(url_for('main.dashboard'))

        flash('Invalid email or password.', 'danger')

    return render_template('login.html')


@bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.login'))


@bp.route('/dashboard')
@login_required
def dashboard():
    balances = LeaveBalance.get_all_balances(session['user_id'])
    recent = LeaveRequest.get_by_employee(session['user_id'])[:5]
    return render_template('dashboard.html', balances=balances, recent_requests=recent)


@bp.route('/request-leave', methods=['GET', 'POST'])
@login_required
def request_leave():
    if request.method == 'POST':
        leave_type = request.form.get('leave_type', '')
        start_date = request.form.get('start_date', '')
        end_date = request.form.get('end_date', '')
        reason = request.form.get('reason', '')
        has_document = 'has_document' in request.form

        employee = Employee.get_by_id(session['user_id'])
        success, message, leave_req = process_leave_request(
            employee, leave_type, start_date, end_date, has_document, reason
        )

        if success:
            flash(message, 'success')
            return redirect(url_for('main.leave_history'))
        else:
            flash(message, 'danger')

    return render_template('request_leave.html',
                           leave_types=LeaveRequest.VALID_LEAVE_TYPES)


@bp.route('/leave-history')
@login_required
def leave_history():
    requests = LeaveRequest.get_by_employee(session['user_id'])
    return render_template('leave_history.html', requests=requests)


@bp.route('/cancel/<int:request_id>', methods=['POST'])
@login_required
def cancel_request(request_id):
    leave_req = LeaveRequest.get_by_id(request_id)

    if not leave_req:
        flash('Leave request not found.', 'danger')
        return redirect(url_for('main.leave_history'))

    if leave_req.employee_id != session['user_id']:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('main.leave_history'))

    # Only restore balance if the request was previously Approved
    was_approved = leave_req.status == 'Approved'

    success, msg = leave_req.update_status('Cancelled')
    if success:
        if was_approved:
            LeaveBalance.restore(leave_req.employee_id, leave_req.leave_type,
                                 leave_req.days_requested)
        flash('Leave request cancelled.', 'success')
    else:
        flash(msg, 'danger')

    return redirect(url_for('main.leave_history'))


@bp.route('/admin')
@admin_required
def admin_panel():
    pending = LeaveRequest.get_pending()
    return render_template('admin.html', pending_requests=pending)


@bp.route('/admin/approve/<int:request_id>', methods=['POST'])
@admin_required
def approve_request(request_id):
    leave_req = LeaveRequest.get_by_id(request_id)

    if not leave_req:
        flash('Leave request not found.', 'danger')
        return redirect(url_for('main.admin_panel'))

    # Re-check balance before approving
    remaining = calculate_leave_balance(leave_req.employee_id, leave_req.leave_type)
    if leave_req.days_requested > remaining:
        flash(f'Insufficient balance. Employee has {remaining} days remaining.', 'danger')
        return redirect(url_for('main.admin_panel'))

    success, msg = leave_req.update_status('Approved', session['user_id'])
    if success:
        LeaveBalance.deduct(leave_req.employee_id, leave_req.leave_type,
                            leave_req.days_requested)
        flash('Leave request approved.', 'success')
    else:
        flash(msg, 'danger')

    return redirect(url_for('main.admin_panel'))


@bp.route('/admin/reject/<int:request_id>', methods=['POST'])
@admin_required
def reject_request(request_id):
    leave_req = LeaveRequest.get_by_id(request_id)

    if not leave_req:
        flash('Leave request not found.', 'danger')
        return redirect(url_for('main.admin_panel'))

    success, msg = leave_req.update_status('Rejected', session['user_id'])
    if success:
        flash('Leave request rejected.', 'info')
    else:
        flash(msg, 'danger')

    return redirect(url_for('main.admin_panel'))


@bp.route('/admin/mark-taken/<int:request_id>', methods=['POST'])
@admin_required
def mark_taken(request_id):
    leave_req = LeaveRequest.get_by_id(request_id)

    if not leave_req:
        flash('Leave request not found.', 'danger')
        return redirect(url_for('main.admin_panel'))

    success, msg = leave_req.update_status('Taken', session['user_id'])
    if success:
        flash('Leave marked as taken.', 'success')
    else:
        flash(msg, 'danger')

    return redirect(url_for('main.admin_panel'))
