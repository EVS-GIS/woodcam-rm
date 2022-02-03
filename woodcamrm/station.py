import datetime

from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort

from psycopg2.extras import RealDictCursor

from woodcamrm.auth import login_required
from woodcamrm.db import get_db
from .extensions import scheduler

bp = Blueprint('station', __name__, url_prefix='/station')


station_fields = {
        'common_name': {'type': "text", 'required': True, 'friendly_name': 'Station common name', 'value': None},
        'api_name': {'type': "text", 'required': False, 'friendly_name': 'API identifier', 'value': None},
        'monthly_data': {'type': "number", 'required': False, 'friendly_name': 'Monthly data volume (Mb)', 'value': None},
        'reset_day': {'type': "number", 'required': False, 'friendly_name': '4G plan reset day', 'value': None},
        'phone_number': {'type': "text", 'required': False, 'friendly_name': 'Phone number', 'value': None},
        'ip': {'type': "text", 'required': False, 'friendly_name': 'IP', 'value': None},
        'mqtt_prefix': {'type': "text", 'required': False, 'friendly_name': 'MQTT prefix', 'value': None},
        'jan_threshold': {'type': "number", 'required': False, 'friendly_name': 'Water level threshold january', 'value': None},
        'feb_threshold': {'type': "number", 'required': False, 'friendly_name': 'Water level threshold february', 'value': None},
        'mar_threshold': {'type': "number", 'required': False, 'friendly_name': 'Water level threshold march', 'value': None},
        'apr_threshold': {'type': "number", 'required': False, 'friendly_name': 'Water level threshold april', 'value': None},
        'may_threshold': {'type': "number", 'required': False, 'friendly_name': 'Water level threshold may', 'value': None},
        'jun_threshold': {'type': "number", 'required': False, 'friendly_name': 'Water level threshold june', 'value': None},
        'jul_threshold': {'type': "number", 'required': False, 'friendly_name': 'Water level threshold july', 'value': None},
        'aug_threshold': {'type': "number", 'required': False, 'friendly_name': 'Water level threshold august', 'value': None},
        'sep_threshold': {'type': "number", 'required': False, 'friendly_name': 'Water level threshold september', 'value': None},
        'oct_threshold': {'type': "number", 'required': False, 'friendly_name': 'Water level threshold october', 'value': None},
        'nov_threshold': {'type': "number", 'required': False, 'friendly_name': 'Water level threshold november', 'value': None},
        'dec_threshold': {'type': "number", 'required': False, 'friendly_name': 'Water level threshold december', 'value': None}
    }


@bp.route('/')
@login_required
def index():
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "SELECT * FROM stations ORDER BY created DESC;"
    )
    stations = cur.fetchall()
    
    cur.execute(
        "SELECT * FROM jobs ORDER BY priority ASC;"
    )
    jobs = cur.fetchall()
    
    cur.close()
    return render_template('station/index.html', 
                           stations=stations, 
                           selected='dashboard',
                           jobs = jobs)


@bp.route('/add', methods=('GET', 'POST'))
@login_required
def add():
    fields = station_fields
    
    if request.method == 'POST':
        for fd in fields.keys():
            fields[fd]['value'] = request.form[fd]

        error = None

        if not fields['common_name']['value']:
            error = 'A station name is required.'

        if error is not None:
            flash(error)
        else:
            db = get_db()
            
            try:
                insert_into = "".join([f"{fd}, " for fd in fields.keys() if fields[fd]['value']])
                values = "".join([f"'{fields[fd]['value']}', " for fd in fields.keys() if fields[fd]['value']])
                sql = "INSERT INTO stations (" + insert_into[:-2] + ") VALUES (" + values[:-2] + ");"

                cur = db.cursor()
                cur.execute(sql)
                cur.close()
                db.commit()

            except db.IntegrityError:
                error = f"Station {fields['common_name']['value']} is already registered."
            else:
                scheduler.get_job(id ="hydrodata_update").modify(next_run_time=datetime.datetime.now())
                scheduler.get_job(id ="check_data_plan").modify(next_run_time=datetime.datetime.now())
                return redirect(url_for('station.index'))

    return render_template('station/add.html', selected='addstation', fields=fields)


def get_station(id):
    db = get_db()
    cur = db.cursor(cursor_factory=RealDictCursor)
    cur.execute(f"SELECT * FROM stations WHERE id = {id};")
    station = cur.fetchone()

    if station is None:
        abort(404, f"Station {id} doesn't exist.")

    return station


@bp.route('/<int:id>', methods=('GET', 'POST'))
@login_required
def station(id):
    station = get_station(id)
    
    return render_template('station/station.html', station=station, selected=id, fields=station_fields)


@bp.route('/<int:id>/update', methods=('GET', 'POST'))
@login_required
def update(id):
    station = get_station(id)
    fields = station_fields

    if request.method == 'GET':
        for fd in fields.keys():
            fields[fd]['value'] = station[fd]

    elif request.method == 'POST':
        for fd in fields.keys():
            fields[fd]['value'] = request.form[fd]

        error = None

        if not fields['common_name']['value']:
            error = 'A station name is required.'

        if error is not None:
            flash(error)
        else:
            db = get_db()
            
            try:
                data_sql = "".join([f"{fd} = '{fields[fd]['value']}', " for fd in fields.keys() if fields[fd]['value']])
                sql = "UPDATE stations SET " + data_sql[:-2] + f" WHERE id = {id};"

                cur = db.cursor()
                cur.execute(sql)
                cur.close()
                db.commit()

            except db.IntegrityError:
                error = f"Station {fields['common_name']['value']} already exists."
            else:
                scheduler.get_job(id ="hydrodata_update").modify(next_run_time=datetime.datetime.now())
                scheduler.get_job(id ="check_data_plan").modify(next_run_time=datetime.datetime.now())
                return redirect(url_for('station.index'))

    return render_template('station/update.html', station=station, selected=id, fields=fields)


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