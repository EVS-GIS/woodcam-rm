from threading import current_thread
import requests
import datetime

import paho.mqtt.publish as publish

from flask import (
    Blueprint, redirect, url_for
)
from werkzeug.exceptions import abort

from psycopg2.extras import RealDictCursor
from pysnmp.hlapi import *

from woodcamrm.auth import login_required
from woodcamrm.extensions import scheduler
from woodcamrm.db import get_db

bp = Blueprint('jobs', __name__, url_prefix='/jobs')


@scheduler.task(
    "interval",
    id="hydrodata_update",
    seconds=60*30,
    max_instances=1,
    start_date="2022-01-01 12:00:00",
)
def hydrodata_update():
    """This job update the hydro metrics and check if the thresholds are triggered.
    """
    with scheduler.app.app_context():
        db = get_db()
        cur = db.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM stations;")
        stations = cur.fetchall()
        
        for st in stations:
            # Check if API_name is informed for the station
            if st['api_name']:
                
                # Request external API
                rep = requests.get(scheduler.app.config["API_URI"],
                                data={"code_entite": st['api_name'],
                                        "grandeur_hydro": "H",
                                        "fields": "date_obs,resultat_obs",
                                        "size": 1})
                hydrodata = rep.json()['data'][0]
                
                # Retrieve trigger threshold for the current month
                current_month = datetime.datetime.now().strftime("%B").lower()[:3] + "_threshold"
                threshold = st[current_month]
                
                # Update current_recording mode and lasttime of recording mode change 
                current_recording = 'unknown'
                trigger_time = st['last_record_change']
                
                # Check if a threshold is informed for the current month
                if threshold:
                    
                    # Check if threshold is triggered
                    if hydrodata['resultat_obs'] >= threshold:
                        # Check if the recording mode is not already "high_flow"
                        if st['current_recording'] != "high_flow":
                            # Update recording mode change time
                            trigger_time = datetime.datetime.now()
                            
                        current_recording = 'high_flow'
                        
                        # Push the recording mode to the MQTT broker
                        publish.single(
                            f"{st['mqtt_prefix']}/flow_trigger",
                            "On",
                            hostname=scheduler.app.config["MQTT_BROKER"],
                            auth={"username": scheduler.app.config["MQTT_USER"], "password": scheduler.app.config["MQTT_PASSWORD"]},
                            port=int(scheduler.app.config["MQTT_PORT"]),
                            qos=1,
                            retain=True,
                        )
                        
                    else:
                        # Check if the recording mode is not already "low_flow"
                        if st['current_recording'] != "low_flow":
                            # Update recording mode change time
                            trigger_time = datetime.datetime.now()
                            
                        current_recording = 'low_flow'
                        
                        # Push the recording mode to the MQTT broker
                        publish.single(
                            f"{st['mqtt_prefix']}/flow_trigger",
                            "Off",
                            hostname=scheduler.app.config["MQTT_BROKER"],
                            auth={"username": scheduler.app.config["MQTT_USER"], "password": scheduler.app.config["MQTT_PASSWORD"]},
                            port=int(scheduler.app.config["MQTT_PORT"]),
                            qos=1,
                            retain=True,
                        )

                # Update the stations table in the database
                cur.execute(
                    f"UPDATE stations SET last_hydro_time = '{hydrodata['date_obs']}', \
                        last_hydro = {hydrodata['resultat_obs']}, \
                        current_recording = '{current_recording}', \
                        last_record_change = '{trigger_time}'\
                    WHERE id = {st['id']};"
                )

        # Update the jobs table in the database
        cur.execute(
            "UPDATE jobs SET last_execution = CURRENT_TIMESTAMP, state = 'running'  WHERE job_name = 'hydrodata_update';"
        )
        db.commit()
        cur.close()


@scheduler.task(
    "interval",
    id="check_data_plan",
    seconds=60*60,
    max_instances=1,
    start_date="2022-01-01 12:00:00",
)
def check_data_plan():
    """Retrieve data usage from router using SNMP protocol.
    """
    with scheduler.app.app_context():
        db = get_db()
        cur = db.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM stations;")
        stations = cur.fetchall()

        for st in stations:
            # Check if station IP is informed
            if st['ip']:    
                total = 0
                
                # Loop over the two OIDs (transmitted and received)
                for oid in [scheduler.app.config["OID_DATA_RECEIVED"], scheduler.app.config["OID_DATA_TRANSMITTED"]]:
                    # Retrieve value from SNMP agent
                    iterator = getCmd(
                        SnmpEngine(),
                        CommunityData('public', mpModel=0),
                        UdpTransportTarget((st['ip'], 161)),
                        ContextData(),
                        ObjectType(ObjectIdentity(oid))
                    )

                    errorIndication, errorStatus, errorIndex, varBinds = next(iterator)

                    if errorIndication:
                        print(errorIndication)
                        cur.execute(
                            "UPDATE jobs SET last_execution = CURRENT_TIMESTAMP, state = 'error' WHERE job_name = 'check_data_plan';"
                        )
                        db.commit()
                        cur.close()
                        return
                    elif errorStatus:
                        print('%s at %s' % (errorStatus.prettyPrint(),
                                            errorIndex and varBinds[int(errorIndex) - 1][0] or '?'))
                        cur.execute(
                            "UPDATE jobs SET last_execution = CURRENT_TIMESTAMP, state = 'error' WHERE job_name = 'check_data_plan';"
                        )
                        db.commit()
                        cur.close()
                        return
                    else:
                        # Add value to total
                        total += int(varBinds[0][1])

                # Convert total from bytes to Mb
                total = total * 10**-6
                
                # Update stations table on the database
                cur.execute(
                    f"UPDATE stations SET current_data = {total}, last_data_check = CURRENT_TIMESTAMP WHERE id = {st['id']};"
                )

        # Update jobs table on the database
        cur.execute(
            "UPDATE jobs SET last_execution = CURRENT_TIMESTAMP, state = 'running' WHERE job_name = 'check_data_plan';"
        )
        db.commit()
        cur.close()


# Manual jobs operations

@bp.route('/<job>/run')
@login_required
def manual_run(job):
    scheduler.get_job(id = job).modify(next_run_time=datetime.datetime.now())
    return redirect(url_for('station.index'))


@bp.route('/<job>/stop')
@login_required
def manual_stop(job):
    scheduler.get_job(id = job).pause()

    with scheduler.app.app_context():
        db = get_db()
        cur = db.cursor()    
        cur.execute(f"UPDATE jobs SET state = 'stopped' WHERE job_name = '{job}';")
        db.commit()
        cur.close()
    
    return redirect(url_for('station.index'))


@bp.route('/<job>/resume')
@login_required
def manual_resume(job):
    scheduler.get_job(id = job).resume()

    with scheduler.app.app_context():
        db = get_db()
        cur = db.cursor()    
        cur.execute(f"UPDATE jobs SET state = 'running' WHERE job_name = '{job}';")
        db.commit()
        cur.close()
    
    return redirect(url_for('station.index'))


# @scheduler.task(
#     "interval",
#     id="records_check",
#     seconds=60,
#     max_instances=1,
#     start_date="2022-01-01 12:00:00",
# )
# def records_check():
#     with scheduler.app.app_context():
#         db = get_db()
#         cur = db.cursor(cursor_factory=RealDictCursor)
#         cur.execute("SELECT * FROM stations;")
#         stations = cur.fetchall()

#         for st in stations:
#             # ssh_client = paramiko.SSHClient()
#             record_files = glob.glob(
#                 os.path.join(st["records_path"], "**/*"), recursive=True
#             )

#             if not record_files:
#                 break

#             cur.execute(f"SELECT * FROM records WHERE station_id = {st['id']};")
#             record_known = [rec["path"] for rec in cur.fetchall()]

#             if record_known:
#                 new_records = [r for r in record_files if r not in record_known]
#                 deleted_records = [r for r in record_known if r not in record_files]
#             else:
#                 new_records = record_files
#                 deleted_records = None

#             for nr in new_records:
#                 output = subprocess.check_output(
#                     f"exiftool -d '%Y-%m-%d %H:%M:%S %Z' {nr}", shell=True
#                 )
#                 lines = output.decode("ascii").split("\n")
#                 lines = [li for li in lines if li != ""]

#                 keys = [li.split(" : ")[0].rstrip() for li in lines]
#                 values = [li.split(" : ")[1] for li in lines]

#                 meta = dict(zip(keys, values))

#                 cur.execute(
#                     f"INSERT INTO records (station_id, date_begin, date_end, size, path) VALUES \
#                     ({st['id']}, \
#                     '{meta['Date/Time Original']}', \
#                     '{meta['File Modification Date/Time']}', \
#                     '{meta['File Size']}', \
#                     '{nr}');"
#                 )

#             for dr in deleted_records:
#                 cur.execute(
#                     f"UPDATE records set deleted = True \
#                     WHERE station_id = {st['id']} AND path = {dr};"
#                 )

#         cur.execute(
#             "UPDATE jobs SET last_execution = CURRENT_TIMESTAMP \
#             WHERE job_name = 'records_check';"
#         )
#         db.commit()
#         cur.close()


# @scheduler.task(
#     "interval",
#     id="alive_check",
#     seconds=60,
#     max_instances=1,
#     start_date="2022-01-01 12:00:00",
# )
# def alive_check():
#     with scheduler.app.app_context():
#         db = get_db()
#         cur = db.cursor()
#         cur.execute(
#             "UPDATE jobs SET last_execution = CURRENT_TIMESTAMP, state = 'running'  WHERE job_name = 'alive_check';"
#         )
#         db.commit()
#         cur.close()