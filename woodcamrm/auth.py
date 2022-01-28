import functools

from psycopg2.extras import RealDictCursor

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

from woodcamrm.db import get_db

bp = Blueprint('auth', __name__, url_prefix='/auth')


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))

        return view(**kwargs)

    return wrapped_view


@bp.route('/register', methods=('GET', 'POST'))
@login_required
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        db = get_db()
        error = None

        if not username:
            error = 'Username is required.'
        elif not password:
            error = 'Password is required.'

        if error is None:
            try:
                cur = db.cursor()
                cur.execute(
                    f"INSERT INTO users (username, password, role) VALUES ('{username}', '{generate_password_hash(password)}', '{role}');"
                )
                db.commit()
                cur.close()
            except db.IntegrityError:
                error = f"User {username} is already registered."
            else:
                return redirect(url_for("auth.login"))

        flash(error)

    return render_template('auth/register.html')


@bp.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        cur = db.cursor(cursor_factory=RealDictCursor)
        error = None
        cur.execute(
            f"SELECT * FROM users WHERE username = '{username}';"
        )
        user = cur.fetchone()
        cur.close()

        if user is None:
            error = 'Incorrect username.'
        elif not check_password_hash(user['password'], password):
            error = 'Incorrect password.'

        if error is None:
            session.clear()
            session['user_id'] = user['id']
            return redirect(url_for('index'))

        flash(error)

    return render_template('auth/login.html')


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        db = get_db()
        cur = db.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            f'SELECT * FROM users WHERE id = {user_id};'
        )
        g.user = cur.fetchone()
        cur.close()
        
        
@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))
