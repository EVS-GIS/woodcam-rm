from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort

from psycopg2.extras import RealDictCursor

from woodcamrm.auth import login_required
from woodcamrm.db import get_db

bp = Blueprint('station', __name__)


@bp.route('/')
def index():
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "SELECT * FROM stations ORDER BY created DESC;"
    )
    stations = cur.fetchall()
    cur.close()
    return render_template('station/index.html', stations=stations)


@bp.route('/add', methods=('GET', 'POST'))
@login_required
def add():
    if request.method == 'POST':
        common_name = request.form['common_name']
        api_name = request.form['api_name']
        monthly_data = request.form['monthly_data']
        reset_day = request.form['reset_day']
        phone_number = request.form['phone_number']
        ip = request.form['ip']
        proxy = request.form['proxy']
        error = None

        if not common_name:
            error = 'A station name is required.'

        if error is not None:
            flash(error)
        else:
            db = get_db()
            
            try:
                cur = db.cursor()
                cur.execute(
                    f"INSERT INTO stations (common_name, api_name, monthly_data, reset_day, phone_number, ip, proxy) \
                    VALUES ('{common_name}', '{api_name}', {monthly_data}, {reset_day}, '{phone_number}', '{ip}', '{proxy}');"
                )
                cur.close()
                db.commit()
            except db.IntegrityError:
                error = f"Station {common_name} is already registered."
            else:
                return redirect(url_for('station.index'))

    return render_template('station/add.html')


def get_station(id):
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute(f"SELECT * FROM stations WHERE id = {id};")
    station = cur.fetchone()

    if station is None:
        abort(404, f"Station {id} doesn't exist.")

    return station


@bp.route('/<int:id>/update', methods=('GET', 'POST'))
@login_required
def update(id):
    station = get_station(id)

    if request.method == 'POST':
        common_name = request.form['common_name']
        api_name = request.form['api_name']
        monthly_data = request.form['monthly_data']
        reset_day = request.form['reset_day']
        phone_number = request.form['phone_number']
        ip = request.form['ip']
        proxy = request.form['proxy']
        error = None

        if not common_name:
            error = 'A station name is required.'

        if error is not None:
            flash(error)
        else:
            db = get_db()
            
            try:
                cur = db.cursor()
                cur.execute(
                    f"UPDATE stations SET \
                        common_name = {common_name}\
                        api_name = {api_name}\
                        monthly_data = {monthly_data}\
                        reset_day = {reset_day}\
                        phone_number = {phone_number}\
                        ip = {ip}\
                        proxy = {proxy}\
                    WHERE id = {id};"
                )
                cur.close()
                db.commit()
            except db.IntegrityError:
                error = f"Station {common_name} already exists."
            else:
                return redirect(url_for('station.index'))

    return render_template('station/update.html', station=station)


@bp.route('/<int:id>/delete', methods=('POST',))
@login_required
def delete(id):
    get_station(id)
    db = get_db()
    cur = db.cursor()
    cur.execute(f"DELETE FROM stations WHERE id = {id};")
    cur.close()
    db.commit()
    return redirect(url_for('station.index'))