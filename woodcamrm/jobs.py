import os
import socket
import requests
import redis
import time
import json

from datetime import datetime
from suntime import Sun

from flask import Blueprint, redirect, url_for

from pysnmp.hlapi import *

from woodcamrm import save_video_file
from woodcamrm.auth import login_required
from woodcamrm.extensions import scheduler, dbsql
from woodcamrm.db import RecordMode, Stations, Jobs, PlannedRecoveries

bp = Blueprint("jobs", __name__, url_prefix="/jobs")


@scheduler.task(
    "interval",
    id="hydrodata_update",
    seconds=60 * 30,
    max_instances=1,
    start_date="2022-01-01 12:00:00",
)
def hydrodata_update():
    """This job update the hydro metrics and check if the thresholds are triggered."""
    with scheduler.app.app_context():
        jb = Jobs.query.filter_by(job_name="hydrodata_update").first()
        jb.last_execution = datetime.now()
        jb.state = 0
        dbsql.session.commit()
        
        stations = Stations.query.all()

        for st in stations:
            # Check if API_name is informed for the station
            if st.api_name:

                # Request external API
                rep = requests.get(
                    scheduler.app.config["API_URI"],
                    data={
                        "code_entite": st.api_name,
                        "grandeur_hydro": "H",
                        "fields": "date_obs,resultat_obs",
                        "size": 1,
                    },
                )
                
                try:
                    hydrodata = rep.json()["data"][0]
                except requests.JSONDecodeError:
                    jb.state = 1
                    jb.message = f'Bad API response for station {st.common_name}'
                    continue
                except IndexError:
                    jb.state = 1
                    jb.message = f'Empty API response for station {st.common_name}'
                    continue

                # Retrieve trigger threshold for the current month
                current_month = datetime.now().strftime("%B").lower()[:3] + "_threshold"
                threshold = getattr(st, current_month)

                # Update current_recording mode and lasttime of recording mode change
                current_recording = 0
                trigger_time = st.last_record_change
                change = False

                # Check if a threshold is informed for the current month
                if threshold is not None:
                    # Check if threshold is triggered
                    if hydrodata["resultat_obs"] >= threshold:
                        # Check if the recording mode is not already "high_flow"
                        if st.current_recording != 2:
                            change = True
                            # Update recording mode change time
                            trigger_time = datetime.now()

                        current_recording = 2
                    
                    # If no threshold triggered, set recording to low flow 
                    else:
                        # Check if the recording mode is not already "low_flow"
                        if st.current_recording != 1:
                            change = True
                            # Update recording mode change time
                            trigger_time = datetime.now()

                        current_recording = 1

                # Update the stations table in the database
                st.last_hydro_time = datetime.strptime(
                    hydrodata["date_obs"], "%Y-%m-%dT%H:%M:%SZ"
                )
                st.last_hydro = hydrodata["resultat_obs"]
                st.current_recording = current_recording
                st.last_record_change = trigger_time
                dbsql.session.commit()

        # Update the jobs table in the database
        jb.last_execution = datetime.now()
        if jb.state == 0:
            jb.state = 4
            jb.message = 'running'
        dbsql.session.commit()


@scheduler.task(
    "interval",
    id="alive_check",
    seconds=120,
    max_instances=1,
    start_date="2022-01-01 12:00:00",
)
def alive_check():
    with scheduler.app.app_context():
        stations = Stations.query.filter(Stations.ip != None).all()
        jb = Jobs.query.filter_by(job_name="alive_check").first()
        jb.last_execution = datetime.now()
        jb.state = 0
        dbsql.session.commit()
        
        output_ping_targets = []
        output_snmp_targets = []
        
        # Retrieve data usage status from prometheus database
        # rep = requests.get(f"{scheduler.app.config['PROMETHEUS_URL']}/api/v1/query", 
        #             auth=(scheduler.app.config['DEFAULT_USER'], scheduler.app.config['DEFAULT_PASSWORD']),
        #             params={'query':'sum by (common_name) (increase(dataTransmitted[31d])+increase(dataReceived[31d]))'})
        # data_usage = rep.json()
            
        for st in stations:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)

            # Retrieve ping status from prometheus database
            # rep = requests.get(f"{scheduler.app.config['PROMETHEUS_URL']}/api/v1/query", 
            #         auth=(scheduler.app.config['DEFAULT_USER'], scheduler.app.config['DEFAULT_PASSWORD']),
            #         params={'query':'probe_success{common_name="'+st.common_name+'", hardware="camera"}'})
                
            # if rep.json()['data']['result'][0]['value'][1] == 1:
            #     st.ping_alert = False
            #     st.last_ping = rep.json()['data']['result'][0]['value'][0]
            # else:
            #     st.ping_alert = True
            st.ping_alert=False
                
            # Update data usage
            #TODO
                    
            # If coordinates are set, update daymode
            if st.long and st.lat:

                sun = Sun(lat=float(st.lat), lon=float(st.long))
                sunrise = sun.get_local_sunrise_time()
                sunset = sun.get_local_sunset_time()

                now = datetime.now(sunrise.tzinfo)

                change = False
                if now < sunrise or now > sunset:
                    if st.current_daymode == 1:
                        change = True
                    st.current_daymode = 0
                else:
                    if st.current_daymode == 0:
                        change = True
                    st.current_daymode = 1

                dbsql.session.commit()
                
            # Add entry for ping_targets.json file
            output_ping_targets.append(
                {
                    'targets': [f'{st.ip}:{st.camera_port}'], 
                    'labels': {'common_name': f'{st.common_name}', 'hardware': 'camera'}
                })
            output_ping_targets.append(
                {
                    'targets': [f'{st.ip}:{st.installation_port}'], 
                    'labels': {'common_name': f'{st.common_name}', 'hardware': 'router'}
                })
            
            # Add entry for snmp_targets.json file
            if st.snmp_monitoring:
                output_snmp_targets.append(
                    {
                        'targets': [f'{st.ip}'], 
                        'labels': {'common_name': f'{st.common_name}'}
                    })
            

        # Check if ping_targets.json have changed
        if os.path.isfile('/etc/prometheus/ping_targets.json'):
            with open('/etc/prometheus/ping_targets.json', 'r') as file:
                ping_targets = json.load(file)
        else:
            ping_targets = []
        
        if ping_targets != output_ping_targets:
            with open('/etc/prometheus/ping_targets.json', 'w') as file:
                json.dump(output_ping_targets, file)
                
        
        # Check if snmp_targets.json have changed
        if os.path.isfile('/etc/prometheus/snmp_targets.json'):
            with open('/etc/prometheus/snmp_targets.json', 'r') as file:
                snmp_targets = json.load(file)
        else:
            snmp_targets = []
        
        if snmp_targets != output_snmp_targets:
            with open('/etc/prometheus/snmp_targets.json', 'w') as file:
                json.dump(output_snmp_targets, file)
                
        
        # Update the jobs table in the database
        jb.last_execution = datetime.now()
        jb.state = 4
        dbsql.session.commit()


@scheduler.task(
    "interval",
    id="records_check",
    seconds=60,
    max_instances=1,
    start_date="2022-01-01 12:00:00",
)
def records_check():
    with scheduler.app.app_context():
        jb = Jobs.query.filter_by(job_name="records_check").first()
        jb.last_execution = datetime.now()
        jb.state = 0
        dbsql.session.commit()
        
        r = redis.from_url(scheduler.app.config["CELERY_BROKER_URL"])

        # List RTSP enabled stations with storage path
        stations = Stations.query.filter(Stations.storage_path != None).filter(Stations.rtsp_url != None).all()

        for st in stations:
            if not os.path.isdir(st.storage_path):
                os.mkdir(st.storage_path)
            
            last_record = r.get(f"station_{st.id}:last_record")
            record_status = r.get(f"station_{st.id}:record_task:status")
            record_task = r.get(f"station_{st.id}:record_task:id")

            running_task = False
            if record_task:
                if record_status not in [b"error", b"success"]:
                    if last_record:
                        if time.time() < (float(last_record) + 65):
                            running_task = True

            # Disable recording at night
            if st.current_daymode == 1:
                r.set(f"station_{st.id}:record_mode", RecordMode(st.current_recording).name)
            else:
                r.set(f"station_{st.id}:record_mode", "no")

            if not running_task and st.current_daymode == 1:
                if st.current_recording == 2:
                    res = save_video_file.delay(
                        filepath=st.storage_path,
                        rtsp_url=st.rtsp_url,
                        station_id=st.id,
                    )

                    r.set(f"station_{st.id}:record_task:id", res.id)
                    
                elif st.current_recording == 1:
                    if not last_record or time.time() > (float(last_record) + 1800):
                        res = save_video_file.delay(
                            filepath=st.storage_path,
                            rtsp_url=st.rtsp_url,
                            station_id=st.id,
                        )
                        
                        r.set(f"station_{st.id}:record_task:id", res.id)
                    
                else:
                    pass

            # Remove clips older than 15min
            old_clips = [os.path.join(st.storage_path, f) for f in os.listdir(st.storage_path) 
                         if time.time() - os.stat(os.path.join(st.storage_path, f)).st_mtime >= (15*60)
                         and not os.path.isdir(os.path.join(st.storage_path, f))]
            
            for clip in old_clips:
                os.remove(clip)
            
            # Remove archive clips older than 1hour
            archives_dir = os.path.join(st.storage_path, 'archives')
            if os.path.isdir(archives_dir):
                old_clips = [os.path.join(archives_dir, f) for f in os.listdir(archives_dir) 
                            if time.time() - os.stat(os.path.join(archives_dir, f)).st_mtime >= (60*60)
                            and not os.path.isdir(os.path.join(archives_dir, f))]
                
                for clip in old_clips:
                    os.remove(clip)
                
            # Remove recovered clips older than 1hour
            recovery_dir = os.path.join(st.storage_path, 'recovery')
            if os.path.isdir(recovery_dir):
                recovered_clips = [os.path.join(recovery_dir, f) for f in os.listdir(recovery_dir) 
                            if time.time() - os.stat(os.path.join(recovery_dir, f)).st_mtime >= (60*60)
                            and not os.path.isdir(os.path.join(recovery_dir, f))]
                
                for clip in recovered_clips:
                    os.remove(clip)
                
        # Update the jobs table in the database
        jb.last_execution = datetime.now()
        jb.state = 4
        dbsql.session.commit()
  
        
@scheduler.task(
    "cron",
    id="recover_data",
    max_instances=1,
    minute='30',
    hour='23'
)
def recover_data():
    with scheduler.app.app_context():
        
        stations = Stations.query.filter(Stations.storage_path != None).all()

        for st in stations:
            #TODO: Check prometheus data to plan recovery automatically
            #TODO: Parallelize by station
            
            planned_rec = PlannedRecoveries.query.filter(PlannedRecoveries.common_name == st.common_name).all()
            
            if planned_rec:
                for record in planned_rec:
                    r = requests.post(f'http://127.0.0.1:5000/api/v1/datarecovery/download_record',
                                auth= (scheduler.app.config["DEFAULT_USER"],scheduler.app.config["DEFAULT_PASSWORD"]),
                                data={'station': record.common_name,
                                      'from_date': record.from_date.strftime('%Y-%m-%dT%H:%M:%S%z'),
                                      'to_date': record.to_date.strftime('%Y-%m-%dT%H:%M:%S%z')})
                    
                    if r.status_code == 200:
                        dbsql.session.delete(record)
                        dbsql.commit()
                
  
########################
# Manual jobs operations
########################


@bp.route("/<job>/run")
@login_required
def manual_run(job):
    scheduler.get_job(id=job).modify(next_run_time=datetime.now())
    return redirect(url_for("station.index"))


@bp.route("/<job>/stop")
@login_required
def manual_stop(job):
    scheduler.get_job(id=job).pause()

    with scheduler.app.app_context():
        jb = Jobs.query.filter_by(job_name=job).first()
        jb.state = 3
        dbsql.session.commit()

    return redirect(url_for("station.index"))


@bp.route("/<job>/resume")
@login_required
def manual_resume(job):
    scheduler.get_job(id=job).resume()

    jb = Jobs.query.filter_by(job_name=job).first()
    jb.state = 4
    dbsql.session.commit()

    return redirect(url_for("station.index"))
