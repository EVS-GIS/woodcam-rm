import os
import glob
import subprocess
import requests

from psycopg2.extras import RealDictCursor

from woodcamrm.extensions import scheduler
from woodcamrm.db import get_db


@scheduler.task(
    "interval",
    id="alive_check",
    seconds=60,
    max_instances=1,
    start_date="2022-01-01 12:00:00",
)
def alive_check():
    with scheduler.app.app_context():
        db = get_db()
        cur = db.cursor()
        cur.execute(
            "UPDATE jobs SET last_execution = CURRENT_TIMESTAMP WHERE job_name = 'alive_check';"
        )
        db.commit()
        cur.close()


@scheduler.task(
    "interval",
    id="hydrodata_update",
    seconds=60*30,
    max_instances=1,
    start_date="2022-01-01 12:00:00",
)
def hydrodata_update():
    with scheduler.app.app_context():
        db = get_db()
        cur = db.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM stations;")
        stations = cur.fetchall()
        
        for st in stations:
            if st['api_name']:
                rep = requests.get(scheduler.app.config["API_URI"],
                                data={"code_entite": st['api_name'],
                                        "grandeur_hydro": "H",
                                        "fields": "date_obs,resultat_obs",
                                        "size": 1})
                hydrodata = rep.json()['data'][0]
                
                #TODO: Check si la valeur est au dessus ou en dessous du seuil pour le mois en cours puis:
                # 1) update la table stations
                # 2) envoyer un push sur MQTT

                cur.execute(
                    f"UPDATE stations SET last_hydro_time = '{hydrodata['date_obs']}', last_hydro = {hydrodata['resultat_obs']} WHERE id = {st['id']};"
                )
            else:
                cur.execute(
                    f"UPDATE stations SET last_hydro_time = CURRENT_TIMESTAMP, last_hydro = 0 WHERE id = {st['id']};"
                )


        cur.execute(
            "UPDATE jobs SET last_execution = CURRENT_TIMESTAMP WHERE job_name = 'hydrodata_update';"
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
    '''
    Retrieve data usage from router using SNMP protocol.
    '''
    with scheduler.app.app_context():
        db = get_db()
        cur = db.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM stations;")
        stations = cur.fetchall()

        for st in stations:
            if st['ip']:
                oid_received = scheduler.app.config["OID_DATA_RECEIVED"]
                oid_transmitted = scheduler.app.config["OID_DATA_TRANSMITTED"]
                received = subprocess.check_output(
                        f"snmpget -v1 -c public {st['ip']} {oid_received}", shell=True
                    ).split(b": ")[1]
                transmitted = subprocess.check_output(
                        f"snmpget -v1 -c public {st['ip']} {oid_transmitted}", shell=True
                    ).split(b": ")[1]
                total = (int(received) + int(transmitted)) * 10**-6

                cur.execute(
                    f"UPDATE stations SET current_data = {total}, last_data_check = CURRENT_TIMESTAMP WHERE id = {st['id']};"
                )
    
        cur.execute(
            "UPDATE jobs SET last_execution = CURRENT_TIMESTAMP WHERE job_name = 'check_data_plan';"
        )
        db.commit()
        cur.close()

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
