from cgi import test
import os
import socket
from threading import current_thread
import requests
import redis
import time

from ftplib import FTP, error_perm
from datetime import datetime
from suntime import Sun
from moviepy.editor import VideoFileClip, concatenate_videoclips

from flask import Blueprint, redirect, url_for
from flask_mail import Message

from pysnmp.hlapi import *

from woodcamrm import save_video_file
from woodcamrm.auth import login_required
from woodcamrm.extensions import scheduler, dbsql, mqtt, mail
from woodcamrm.db import Stations, Jobs, Users

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
        jb.state = "warn"
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
                hydrodata = rep.json()["data"][0]

                # Retrieve trigger threshold for the current month
                current_month = datetime.now().strftime("%B").lower()[:3] + "_threshold"
                threshold = getattr(st, current_month)

                # Update current_recording mode and lasttime of recording mode change
                current_recording = "no"
                trigger_time = st.last_record_change
                change = False

                # Check if a threshold is informed for the current month
                if threshold:
                    # Check if threshold is triggered and daymode is 1
                    if hydrodata["resultat_obs"] >= threshold and st.current_daymode == 1:
                        # Check if the recording mode is not already "high_flow"
                        if st.current_recording.name != "high":
                            change = True
                            # Update recording mode change time
                            trigger_time = datetime.now()

                        current_recording = "high"
                        # Push the recording mode to the MQTT broker
                        if st.mqtt_prefix != None:
                            mqtt.publish(
                                f"{st.mqtt_prefix}/flow_trigger",
                                "On",
                                qos=1,
                                retain=True,
                            )
                    
                    # Disable recording at night
                    elif st.current_daymode == 0:
                        # Check if the recording mode is not already "no"
                        if st.current_recording.name != "no":
                            change = True
                            # Update recording mode change time
                            trigger_time = datetime.now()

                        current_recording = "no"
                    
                    # If not night and no threshold triggered, set recording to low flow 
                    else:
                        # Check if the recording mode is not already "low_flow"
                        if st.current_recording.name != "low":
                            change = True
                            # Update recording mode change time
                            trigger_time = datetime.now()

                        current_recording = "low"

                        # Push the recording mode to the MQTT broker
                        if st.mqtt_prefix != None:
                            mqtt.publish(
                                f"{st.mqtt_prefix}/flow_trigger",
                                "Off",
                                qos=1,
                                retain=True,
                            )

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
        jb.state = "running"
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
        jb.state = "warn"
        dbsql.session.commit()

        stations = Stations.query.all()
        
        for st in stations:
            # Check if station IP is informed
            if st.ip and (st.snmp_received or st.snmp_transmitted):
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
                        jb.state = "error"
                        dbsql.session.commit()
                        return
                    elif errorStatus:
                        print(
                            "%s at %s"
                            % (
                                errorStatus.prettyPrint(),
                                errorIndex and varBinds[int(errorIndex) - 1][0] or "?",
                            )
                        )
                        jb.last_execution = datetime.now()
                        jb.state = "error"
                        dbsql.session.commit()
                        return
                    else:
                        # Add value to total
                        total += int(varBinds[0][1])

                # Convert total from bytes to Mb
                total = total * 10**-6

                # Mail alert if data limit is soon reached
                if st.monthly_data - total < st.monthly_data * 0.05:
                    msg = Message(
                        f"[woodcam-rm] Alert on station {st.common_name}",
                        body=f"The data consumtion of station {st.common_name} reached {total} over the {st.monthly_data} available.",
                    )

                    for user in Users.query.filter_by(notify=True).all():
                        msg.add_recipient(user.email)

                    mail.send(msg)

                # Update stations table on the database
                st.current_data = total
                st.last_data_check = datetime.now()
                dbsql.session.commit()

        # Update the jobs table in the database
        jb.last_execution = datetime.now()
        jb.state = "running"
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
        jb.state = "warn"
        dbsql.session.commit()

        for st in stations:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)

            # First, try to ping camera
            try:
                if not st.camera_port:
                    st.camera_port = 80

                s.connect((st.ip, int(st.camera_port)))
                s.shutdown(2)
                response = True
            except:
                response = False

            if response:
                if st.ping_alert:
                    msg = Message(
                        f"[woodcam-rm] Station {st.common_name} OK",
                        body=f"Station {st.common_name} unreachable from {st.last_ping} to {datetime.now()}.",
                    )

                    for user in Users.query.filter_by(notify=True).all():
                        msg.add_recipient(user.email)

                    mail.send(msg)

                    st.ping_alert = False
                    st.last_ping = datetime.now()

                else:
                    st.last_ping = datetime.now()

            elif not st.ping_alert:
                # If camera does not respond, try to ping installation
                try:
                    if not st.installation_port:
                        st.installation_port = 80

                    s.connect((st.ip, int(st.installation_port)))
                    s.shutdown(2)
                    reponse_install = True
                except:
                    reponse_install = False

                if not reponse_install:
                    msg = Message(
                        f"[woodcam-rm] Alert on station {st.common_name}",
                        body=f"Station {st.common_name}: full installation unreachable since {st.last_ping}.",
                    )

                    for user in Users.query.filter_by(notify=True).all():
                        msg.add_recipient(user.email)

                    mail.send(msg)

                    st.ping_alert = True

                else:
                    msg = Message(
                        f"[woodcam-rm] Alert on station {st.common_name}",
                        body=f"!Critical alert! Station {st.common_name}: camera unreachable since {st.last_ping}. Installation steel reachable.",
                    )

                    for user in Users.query.filter_by(notify=True).all():
                        msg.add_recipient(user.email)

                    mail.send(msg)

                    st.ping_alert = True

            # If all ping are ok, update daymode
            if not st.ping_alert and st.long and st.lat:

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

        # Update the jobs table in the database
        jb.last_execution = datetime.now()
        jb.state = "running"
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
        jb.state = "warn"
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

            if record_task and (record_status not in [b"error", b"success"]):
                running_task = True
            else:
                running_task = False

            if (
                running_task
                and last_record
                and time.time() < float(last_record) + (60 * 2)
            ):
                pass
            elif running_task:
                running_task = False

            r.set(f"station_{st.id}:record_mode", st.current_recording.name)

            if not running_task:
                res = save_video_file.delay(
                    filepath=st.storage_path,
                    rtsp_url=st.rtsp_url,
                    station_id=st.id,
                )

                r.set(f"station_{st.id}:record_task:id", res.id)
                
            # Delete RAM files older than 15min              
            for f in os.listdir(st.storage_path):
                fpath = os.path.join(st.storage_path, f)
                if time.time() - os.stat(fpath).st_mtime > (15 * 60):
                    os.remove(fpath)
                    
        # Update the jobs table in the database
        jb.last_execution = datetime.now()
        jb.state = "running"
        dbsql.session.commit()


@scheduler.task(
    "interval",
    id="download_records",
    seconds=600,
    max_instances=1,
    start_date="2022-01-01 12:00:00",
)
def download_records():
    with scheduler.app.app_context():
        jb = Jobs.query.filter_by(job_name="download_records").first()
        jb.last_execution = datetime.now()
        jb.state = "warn"
        dbsql.session.commit()
        
        stations = Stations.query.filter(Stations.storage_path != None).filter(Stations.rtsp_url != None).all()
        
        for st in stations:
            if not os.path.isdir(st.storage_path):
                continue
            elif not os.listdir(st.storage_path):
                continue
            else:
                src = [os.path.join(st.storage_path, f) for f in os.listdir(st.storage_path)
                        if not os.path.isdir(os.path.join(st.storage_path, f)) 
                        and time.time() - os.stat(os.path.join(st.storage_path, f)).st_mtime > (10*60)]
                
                if not src:
                    continue
                else:
                    # Open source video clips
                    src.sort()
                    src_clips = [VideoFileClip(f) for f in src]
                    
                    if not os.path.isdir(os.path.join(st.storage_path, 'merged_clips')):
                        os.mkdir(os.path.join(st.storage_path, 'merged_clips'))
                    
                    # Concatenate video clips
                    dest = os.path.join(st.storage_path, 'merged_clips', f"archive_video_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.mp4")
                    final = concatenate_videoclips(src_clips, verbose = False)
                    final.write_videofile(dest, verbose = False)
                    
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

                        # Send concatenated video clip to archive server
                        with open(dest, 'rb') as f:
                            ftp.cwd(dst_path)
                            ftp.storbinary('STOR ' + os.path.basename(dest), f)
                            
                    # Remove temp merged video clips
                    os.remove(dest)
                
        # Update the jobs table in the database
        jb.last_execution = datetime.now()
        jb.state = "running"
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
        jb.state = "stopped"
        dbsql.session.commit()

    return redirect(url_for("station.index"))


@bp.route("/<job>/resume")
@login_required
def manual_resume(job):
    scheduler.get_job(id=job).resume()

    jb = Jobs.query.filter_by(job_name=job).first()
    jb.state = "running"
    dbsql.session.commit()

    return redirect(url_for("station.index"))
