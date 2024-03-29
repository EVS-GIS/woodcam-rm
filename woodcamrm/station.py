import os
import glob
import cv2

from datetime import datetime

from flask import (
    Blueprint, redirect, render_template, url_for, Response 
)
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, DecimalField, TelField, BooleanField
from wtforms.validators import DataRequired, Optional, IPAddress

from werkzeug.exceptions import abort

from woodcamrm.auth import login_required
from woodcamrm.db import RecordMode, Stations, Jobs, JobState
from woodcamrm.extensions import dbsql, scheduler

bp = Blueprint('station', __name__, url_prefix='/station')


class StationForm(FlaskForm):
    common_name = StringField('Station common name', validators=[DataRequired()]) 
    api_name = StringField('API identifier', validators=[Optional()]) 
    long = DecimalField('Station longitude', validators=[Optional()])
    lat = DecimalField('Station latitude', validators=[Optional()])
    monthly_data = DecimalField('Monthly data volume (Mb)', validators=[Optional()]) 
    reset_day = IntegerField('4G plan reset day', validators=[Optional()]) 
    phone_number = TelField('Phone number', validators=[Optional()]) 
    ip = StringField('Installation IP', validators=[Optional(), IPAddress()]) 
    api_user = StringField('Camera API authentication user', validators=[Optional()]) 
    api_password = StringField('Camera API authentication password', validators=[Optional()]) 
    storage_path = StringField('Records temp storage path', validators=[Optional()])
    camera_port = IntegerField('Camera ping port', validators=[Optional()])
    installation_port = IntegerField('Installation ping port', validators=[Optional()])
    snmp_monitoring = BooleanField('Enable SNMP Monitoring', validators=[Optional()])
    snmp_received = StringField('SNMP MIB for received data', validators=[Optional()])
    snmp_transmitted = StringField('SNMP MIB for transmitted data', validators=[Optional()])
    
    rtsp_url = StringField('RTSP URL', validators=[Optional()])

    jan_threshold = DecimalField('Water level threshold january (mm)', validators=[Optional()]) 
    feb_threshold = DecimalField('Water level threshold february (mm)', validators=[Optional()]) 
    mar_threshold = DecimalField('Water level threshold march (mm)', validators=[Optional()]) 
    apr_threshold = DecimalField('Water level threshold april (mm)', validators=[Optional()]) 
    may_threshold = DecimalField('Water level threshold may (mm)', validators=[Optional()]) 
    jun_threshold = DecimalField('Water level threshold june (mm)', validators=[Optional()]) 
    jul_threshold = DecimalField('Water level threshold july (mm)', validators=[Optional()]) 
    aug_threshold = DecimalField('Water level threshold august (mm)', validators=[Optional()]) 
    sep_threshold = DecimalField('Water level threshold september (mm)', validators=[Optional()]) 
    oct_threshold = DecimalField('Water level threshold october (mm)', validators=[Optional()]) 
    nov_threshold = DecimalField('Water level threshold november (mm)', validators=[Optional()]) 
    dec_threshold = DecimalField('Water level threshold december (mm)', validators=[Optional()])


def get_station(id):
    station = Stations.query.filter_by(id=id).first()

    if station is None:
        abort(404, f"Station {id} doesn't exist.")

    return station

@bp.route('/')
@login_required
def index():
    stations = Stations.query.all()
    jobs = Jobs.query.all()

    return render_template('station/index.html',
                           stations=stations,
                           selected='dashboard',
                           jobs=jobs,
                           JobState=JobState,
                           RecordMode=RecordMode)


@bp.route('/add', methods=('GET', 'POST'))
@login_required
def add():
    station = Stations()
    form = StationForm(obj=station)
    if form.validate_on_submit():
        form.populate_obj(station)
        
        dbsql.session.add(station)
        dbsql.session.commit()
        
        scheduler.get_job(id="hydrodata_update").modify(
            next_run_time=datetime.now())
        scheduler.get_job(id="alive_check").modify(
            next_run_time=datetime.now())
        
        return redirect(url_for('station.index'))
        
    return render_template('station/add.html', station=station, selected='addstation', form=form)


@bp.route('/<int:id>', methods=('GET', 'POST'))
@login_required
def station(id):
    station = get_station(id)
    form = StationForm(obj=station)

    return render_template('station/station.html', station=station, selected=id, form=form, RecordMode=RecordMode)


@bp.route("/<int:id>/stream")
@login_required
def stream(id):
    station = get_station(id)

    videos = glob.glob(os.path.join(station.storage_path, '*.avi'))
    
    if videos:
        latest = max(videos, key=os.path.getctime)
        
        vid = cv2.VideoCapture(latest)   
        ret, frame = vid.read()
        vid.release()

        _, encodedImage = cv2.imencode(".jpg", frame)
        frame = b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + \
            bytearray(encodedImage) + b'\r\n'

        return Response(frame, mimetype="multipart/x-mixed-replace; boundary=frame")
    
    else:
        return "no stream available"


@bp.route('/<int:id>/update', methods=('GET', 'POST'))
@login_required
def update(id):
    station = get_station(id)
    form = StationForm(obj=station)
    
    if form.validate_on_submit():
        form.populate_obj(station)
        
        dbsql.session.commit()
        
        scheduler.get_job(id="hydrodata_update").modify(
            next_run_time=datetime.now())
        scheduler.get_job(id="alive_check").modify(
            next_run_time=datetime.now())
        scheduler.get_job(id="records_check").modify(
            next_run_time=datetime.now())
        
        return redirect(url_for('station.station', id=id))
        
    return render_template('station/update.html', station=station, selected=id, form=form)
    

@bp.route('/<int:id>/delete', methods=('POST',))
@login_required
def delete(id):
    station = get_station(id)
    dbsql.session.delete(station)
    dbsql.session.commit()

    return redirect(url_for('station.index'))
