import os
import socket
import requests
import redis
import time
import json

from ftplib import FTP, error_perm
from datetime import datetime
from suntime import Sun

from flask import Blueprint, redirect, url_for
from flask_mail import Message

from pysnmp.hlapi import *

from woodcamrm import save_video_file
from woodcamrm.auth import login_required
from woodcamrm.extensions import scheduler, dbsql, mail
from woodcamrm.db import RecordMode, Stations, Jobs, Users

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
    id="check_data_plan",
    seconds=60 * 60,
    max_instances=1,
    start_date="2022-01-01 12:00:00",
)
def check_data_plan():
    """Retrieve data usage from router using SNMP protocol."""
    with scheduler.app.app_context():
        jb = Jobs.query.filter_by(job_name="check_data_plan").first()
        jb.last_execution = datetime.now()
        jb.state = 0
        dbsql.session.commit()

        stations = Stations.query.all()
        
        for st in stations:
            # Check if station IP is informed
            if st.ip and (st.snmp_received or st.snmp_transmitted) and not st.ping_alert:
                total = 0

                # Loop over the two OIDs (transmitted and received)
                for oid in [st.snmp_received, st.snmp_transmitted]:
                    # Retrieve value from SNMP agent
                    iterator = getCmd(
                        SnmpEngine(),
                        CommunityData("public", mpModel=0),
                        UdpTransportTarget((st.ip, 161)),
                        ContextData(),
                        ObjectType(ObjectIdentity(oid)),
                    )

                    errorIndication, errorStatus, errorIndex, varBinds = next(iterator)

                    if errorIndication:
                        print(errorIndication)
                        jb.last_execution = datetime.now()
                        jb.state = 1
                        dbsql.session.commit()
                        continue
                    elif errorStatus:
                        print(
                            "%s at %s"
                            % (
                                errorStatus.prettyPrint(),
                                errorIndex and varBinds[int(errorIndex) - 1][0] or "?",
                            )
                        )
                        jb.last_execution = datetime.now()
                        jb.state = 1
                        dbsql.session.commit()
                        continue
                    else:
                        # Add value to total
                        total += int(varBinds[0][1])

                # Convert total from bytes to Mb
                total = total * 10**-6
                
                if not st.last_data:
                    st.last_data = 0
                    
                # If router total data is lower than last value, the router has probably rebooted
                if total < st.last_data:
                    st.last_data = total    
                    total += float(st.current_data)
                else:
                    to_substract = st.last_data
                    st.last_data = total
                    total -= float(to_substract)
                    total += float(st.current_data)
                    
                # Mail alert if data limit is soon reached
                if st.monthly_data - total < st.monthly_data * 0.05:
                    msg = Message(
                        f"[woodcam-rm] Alert on station {st.common_name}",
                        body=f"The data consumtion of station {st.common_name} reached {total} over the {st.monthly_data} available.",
                    )

                    for user in Users.query.filter_by(notify=True).all():
                        msg.add_recipient(user.email)

                    # mail.send(msg)

                # Update stations table on the database
                st.current_data = total
                st.last_data_check = datetime.now()
                dbsql.session.commit()

        # Update the jobs table in the database
        jb.last_execution = datetime.now()
        if jb.state == 0:
            jb.state = 4
            jb.message = 'running'
        dbsql.session.commit()

#TODO: Task to reset data plan

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
            
        for st in stations:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)

            # Try to ping camera or installation
            if st.camera_port:
                ping_port = st.camera_port
            elif st.installation_port:
                ping_port = st.installation_port
            else:
                ping_port = 80
                
            try:
                s.connect((st.ip, int(ping_port)))
                s.shutdown(2)
                response = True
            except:
                response = False

            if response:
                st.ping_alert = False
                st.last_ping = datetime.now()    
            else:
                st.ping_alert = True
                    
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
        if os.path.isfile('./prometheus/ping_targets.json'):
            with open('./prometheus/ping_targets.json', 'r') as file:
                ping_targets = json.load(file)
        else:
            ping_targets = []
        
        if ping_targets != output_ping_targets:
            with open('./prometheus/ping_targets.json', 'w') as file:
                json.dump(output_ping_targets, file)
                
        
        # Check if snmp_targets.json have changed
        if os.path.isfile('./prometheus/snmp_targets.json'):
            with open('./prometheus/snmp_targets.json', 'r') as file:
                snmp_targets = json.load(file)
        else:
            snmp_targets = []
        
        if snmp_targets != output_snmp_targets:
            with open('./prometheus/snmp_targets.json', 'w') as file:
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
        
        # Update the jobs table in the database
        jb.last_execution = datetime.now()
        jb.state = 4
        dbsql.session.commit()


@scheduler.task(
    "interval",
    id="download_records",
    seconds=600,
    max_instances=1,
    start_date="2022-01-01 12:05:00",
)
def download_records():
    with scheduler.app.app_context():
        jb = Jobs.query.filter_by(job_name="download_records").first()
        jb.last_execution = datetime.now()
        jb.state = 0
        dbsql.session.commit()
        
        stations = Stations.query.filter(Stations.storage_path != None).filter(Stations.rtsp_url != None).all()
        
        for st in stations:
            
            if not os.path.isdir(st.storage_path):
                continue
            
            archives_dir = os.path.join(st.storage_path, "archives")
            
            if not os.path.isdir(archives_dir):
                continue
            elif not os.listdir(archives_dir):
                continue
            
            archives_clips = [os.path.join(archives_dir, f) for f in os.listdir(archives_dir) 
                              if time.time() - os.stat(os.path.join(archives_dir, f)).st_mtime > (5*60)]
            
            # Connection to archive server
            with FTP(scheduler.app.config["ARCHIVE_HOST"], 
                        scheduler.app.config["ARCHIVE_USER"], 
                        scheduler.app.config["ARCHIVE_PASSWORD"]) as ftp:
                
                # Create directory if do not exist
                dst_path = os.path.join(scheduler.app.config["ARCHIVE_PATH"],
                                        st.common_name, 
                                        'woodcamrm-archived-clips', 
                                        datetime.now().strftime('%Y'),
                                        datetime.now().strftime('%m'),
                                        datetime.now().strftime('%d')
                                    )
                
                dirs = []
                testdir = dst_path
                while testdir != "":
                    dirs.append(testdir)
                    testdir = os.path.dirname(testdir)
                
                dirs.reverse()
                
                for dir_checked in dirs:
                    try:
                        ftp.cwd(dir_checked)
                    except error_perm:
                        ftp.mkd(dir_checked)
                    
                    ftp.cwd('/')

                # Send archive clips to archive server
                ftp.cwd(dst_path)
                for clip_file in archives_clips:
                    with open(clip_file, 'rb') as f:
                        ftp.storbinary('STOR ' + os.path.basename(clip_file), f)
                        
                    os.remove(clip_file)
                
        # Update the jobs table in the database
        jb.last_execution = datetime.now()
        jb.state = 4
        dbsql.session.commit()
        
        
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
