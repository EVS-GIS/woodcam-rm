import functools

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)

from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import exc

from woodcamrm.db import Users
from woodcamrm.extensions import dbsql

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

        error = None

        if not username:
            error = 'Username is required.'
        elif not password:
            error = 'Password is required.'

        if error is None:
            try:
                new_user = Users(username=username, password=generate_password_hash(password), role=role)
                
                dbsql.session.add(new_user)
                dbsql.session.commit()

            except exc.IntegrityError:
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
        error = None
        
        user = Users.query.filter_by(username=username).first()

        if user is None:
            error = 'Incorrect username.'
        elif not check_password_hash(user.password, password):
            error = 'Incorrect password.'

        if error is None:
            session.clear()
            session['user_id'] = user.id
            return redirect(url_for('index'))

        flash(error)

    return render_template('auth/login.html')


@bp.route('/settings', methods=('GET', 'POST'))
@login_required
def settings():
    fields = {
        'password': {'type': "password", 'required': False, 'friendly_name': 'Password', 'value': None},
        'email': {'type': "email", 'required': False, 'friendly_name': 'Email', 'value': None},
        'notify': {'type': "checkbox", 'required': False, 'friendly_name': 'Receive mail notifications', 'value': None},
    }
    
    if request.method == 'GET':
        for fd in fields.keys():
            if fd != "password":
                fields[fd]['value'] = getattr(g.user, fd)
    
    if request.method == 'POST':
        
        error = None
        if error is None:
            return redirect(url_for('index'))
        
    return render_template('auth/settings.html', fields=fields)


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        g.user = Users.query.filter_by(id=user_id).first()
        
        
@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))
