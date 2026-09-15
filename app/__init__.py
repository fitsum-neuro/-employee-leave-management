import os
import sqlite3
from flask import Flask, g, current_app


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db(app):
    with app.app_context():
        db = get_db()
        db.executescript('''
            CREATE TABLE IF NOT EXISTS employee (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                department TEXT NOT NULL DEFAULT 'General',
                hire_date TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'employee'
            );

            CREATE TABLE IF NOT EXISTS leave_request (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                leave_type TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                days_requested INTEGER NOT NULL,
                reason TEXT,
                has_document INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Requested',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                reviewed_by INTEGER,
                reviewed_at TEXT,
                FOREIGN KEY (employee_id) REFERENCES employee (id),
                FOREIGN KEY (reviewed_by) REFERENCES employee (id)
            );

            CREATE TABLE IF NOT EXISTS leave_balance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                leave_type TEXT NOT NULL,
                total_days INTEGER NOT NULL DEFAULT 0,
                used_days INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (employee_id) REFERENCES employee (id),
                UNIQUE(employee_id, leave_type)
            );
        ''')
        db.commit()


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod'),
        DATABASE=os.path.join(app.instance_path, 'leave_management.db'),
    )

    if test_config:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)

    app.teardown_appcontext(close_db)

    from . import routes
    app.register_blueprint(routes.bp)

    init_db(app)

    return app
