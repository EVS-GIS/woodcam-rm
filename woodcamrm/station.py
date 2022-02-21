import cv2

from datetime import datetime

from flask import (
    Blueprint, flash, g, Response, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort
from sqlalchemy import exc

from woodcamrm.auth import login_required
from woodcamrm.db import Stations, Jobs
from woodcamrm.extensions import dbsql, scheduler

bp = Blueprint('station', __name__, url_prefix='/station')


station_fields = {
        'common_name': {'type': "text", 'required': True, 'friendly_name': 'Station common name', 'value': None},
        'api_name': {'type': "text", 'required': False, 'friendly_name': 'API identifier', 'value': None},
        'monthly_data': {'type': "number", 'required': False, 'friendly_name': 'Monthly data volume (Mb)', 'value': None},
        'reset_day': {'type': "number", 'required': False, 'friendly_name': '4G plan reset day', 'value': None},
        'phone_number': {'type': "text", 'required': False, 'friendly_name': 'Phone number', 'value': None},
        'ip': {'type': "text", 'required': False, 'friendly_name': 'IP', 'value': None},
        'mqtt_prefix': {'type': "text", 'required': False, 'friendly_name': 'MQTT prefix', 'value': None},
        'jan_threshold': {'type': "number", 'required': False, 'friendly_name': 'Water level threshold january (mm)', 'value': None},
        'feb_threshold': {'type': "number", 'required': False, 'friendly_name': 'Water level threshold february (mm)', 'value': None},
        'mar_threshold': {'type': "number", 'required': False, 'friendly_name': 'Water level threshold march (mm)', 'value': None},
        'apr_threshold': {'type': "number", 'required': False, 'friendly_name': 'Water level threshold april (mm)', 'value': None},
        'may_threshold': {'type': "number", 'required': False, 'friendly_name': 'Water level threshold may (mm)', 'value': None},
        'jun_threshold': {'type': "number", 'required': False, 'friendly_name': 'Water level threshold june (mm)', 'value': None},
        'jul_threshold': {'type': "number", 'required': False, 'friendly_name': 'Water level threshold july (mm)', 'value': None},
        'aug_threshold': {'type': "number", 'required': False, 'friendly_name': 'Water level threshold august (mm)', 'value': None},
        'sep_threshold': {'type': "number", 'required': False, 'friendly_name': 'Water level threshold september (mm)', 'value': None},
        'oct_threshold': {'type': "number", 'required': False, 'friendly_name': 'Water level threshold october (mm)', 'value': None},
        'nov_threshold': {'type': "number", 'required': False, 'friendly_name': 'Water level threshold november (mm)', 'value': None},
        'dec_threshold': {'type': "number", 'required': False, 'friendly_name': 'Water level threshold december (mm)', 'value': None}
    }


@bp.route('/')
@login_required
def index():
    stations = Stations.query.all()
    jobs = Jobs.query.all()
    
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
            new_station = Stations()     
            for fd in fields.keys():
                if fields[fd]['value']:
                    setattr(new_station, fd, fields[fd]['value'])
                    
            try:
                dbsql.session.add(new_station)
                dbsql.session.commit()

            except exc.IntegrityError:
                error = f"Station {fields['common_name']['value']} is already registered."
            else:
                scheduler.get_job(id ="hydrodata_update").modify(next_run_time=datetime.now())
                scheduler.get_job(id ="check_data_plan").modify(next_run_time=datetime.now())
                return redirect(url_for('station.index'))

    return render_template('station/add.html', selected='addstation', fields=fields)


def get_station(id):
    station = Stations.query.filter_by(id=id).first()

    if station is None:
        abort(404, f"Station {id} doesn't exist.")

    return station


@bp.route('/<int:id>', methods=('GET', 'POST'))
@login_required
def station(id):
    station = get_station(id)
    
    return render_template('station/station.html', station=station, selected=id, fields=station_fields)
        
        
@bp.route("/<int:id>/stream")
def stream(id):
    station = get_station(id)
    
    camera = cv2.VideoCapture(f"rtsp://{station.ip}/axis-media/media.amp?resolution=320x240&fps=1")
    success, frame = camera.read()
    
    if not success:
        return Response()
    
    _, encodedImage = cv2.imencode(".jpg", frame)
    frame = b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + bytearray(encodedImage) + b'\r\n'
    
    return Response(frame, mimetype = "multipart/x-mixed-replace; boundary=frame")


@bp.route('/<int:id>/update', methods=('GET', 'POST'))
@login_required
def update(id):
    station = get_station(id)
    fields = station_fields

    if request.method == 'GET':
        for fd in fields.keys():
            fields[fd]['value'] = getattr(station, fd)

    elif request.method == 'POST':
        for fd in fields.keys():
            fields[fd]['value'] = request.form[fd]

        error = None

        if not fields['common_name']['value']:
            error = 'A station name is required.'

        if error is not None:
            flash(error)
        else:         
            try:
                for fd in fields.keys():
                    if fields[fd]['value']:
                        setattr(station, fd, fields[fd]['value'])
                
                dbsql.session.commit()

            except exc.IntegrityError:
                error = f"Station {fields['common_name']['value']} already exists."
                
            else:
                scheduler.get_job(id ="hydrodata_update").modify(next_run_time=datetime.now())
                scheduler.get_job(id ="check_data_plan").modify(next_run_time=datetime.now())
                return redirect(url_for('station.index'))

    return render_template('station/update.html', station=station, selected=id, fields=fields)


@bp.route('/<int:id>/delete', methods=('POST',))
@login_required
def delete(id):
    station = get_station(id)
    dbsql.session.delete(station)
    dbsql.session.commit()
    
    return redirect(url_for('station.index'))