import os
import cv2
import time
import redis

from datetime import datetime
from dotenv import dotenv_values

from flask import Flask

from sqlalchemy import exc

from celery import Celery

from woodcamrm.extensions import mqtt, dbsql, scheduler, mail
from woodcamrm.db import Stations


celery = Celery(__name__, 
                backend=dotenv_values()["CELERY_RESULT_BACKEND"],
                broker=dotenv_values()["CELERY_BROKER_URL"])


def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(dotenv_values())
    app.config['MQTT_BROKER_PORT'] = int(app.config['MQTT_BROKER_PORT'])
    
    for key in app.config.keys():
        if str(app.config[key]).lower() == "true":
            app.config[key] = True
        elif str(app.config[key]).lower() == "false":
            app.config[key] = False

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile("config.py", silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Database
    from . import db

    dbsql.init_app(app)
    db.init_app(app)

    with app.app_context():
        try:
            stations = Stations.query.all()                
        except exc.ProgrammingError:
            stations = []
            print('The database needs to be updated. Please run flask init-db first.')
    
    # Mailing system
    mail.init_app(app)
    
    # APScheluder and Celery for CRON jobs
    scheduler.api_enabled = False
    scheduler.init_app(app)   
        
    with app.app_context():
        from . import jobs
        app.register_blueprint(jobs.bp)
        scheduler.start()
        
        celery.conf.update(app.config)

    # MQTT client
    from . import mqtt_client
    if stations:
        mqtt.init_app(app)

    @mqtt.on_connect()
    def handle_connect(client, userdata, flags, rc):
        with app.app_context():
            stations = Stations.query.filter(Stations.mqtt_prefix != None).all()
            if stations:
                mqtt_client.subscribe_topics(stations)

    @mqtt.on_message()
    def handle_mqtt_message(client, userdata, message):
        with app.app_context():
            stations = Stations.query.filter(Stations.mqtt_prefix != None).all()
            mqtt_data = mqtt_client.to_dict(stations, message)

            setattr(mqtt_data['station'],
                    mqtt_data['topic'], mqtt_data['data'])
                
            dbsql.session.commit()
            
            # Mail alerts
            mqtt_client.alerts(stations)

    @app.context_processor
    def inject_pages():
        return dict(pages=stations)
        
    from . import auth

    app.register_blueprint(auth.bp)

    from . import station

    app.register_blueprint(station.bp)

    from . import home

    app.register_blueprint(home.bp)
    app.add_url_rule("/", endpoint="index")

    return app


#####
# Celery task definition below
####

@celery.task()
def save_video_file(filepath, rtsp_url, station_id):
    
    r = redis.from_url(dotenv_values()["CELERY_BROKER_URL"])
    recording_mode = r.get(f"station_{station_id}:record_mode")
    
    if recording_mode == b'no':
        return 0
    
    r.set(f"station_{station_id}:record_task:status", "started")
    cap = cv2.VideoCapture(rtsp_url)
    
    # Get current width of frame
    width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    # Get current height of frame
    height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    
    # Define the codec and create VideoWriter object
    fourcc = cv2.VideoWriter_fourcc(*'MJPG')
    
    videos_number = 0
    
    while recording_mode == b"high":
        videos_number+=1
        recording_mode = r.get(f"station_{station_id}:record_mode")
        
        # Update redis data
        r.set(f"station_{station_id}:last_record", time.time())
        r.set(f"station_{station_id}:record_task:status", "pending")
        
        # Define output
        filename = os.path.join(filepath, f"video_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_highflow.mkv")
        out = cv2.VideoWriter(filename, fourcc, 3, (int(width),int(height)))
        
        timeout = time.time() + 60
        while time.time() < timeout:
            ret, frame = cap.read()
            
            if ret == True:
                out.write(frame)
                
            else:
                r.set(f"station_{station_id}:record_task:status", "error")
                raise Exception("Stream unreachable!")
            
        out.release()
    
    if recording_mode == b"low":
        videos_number+=1
        r.set(f"station_{station_id}:last_record", time.time())
        r.set(f"station_{station_id}:record_task:status", "pending")
        
        # Define output
        filename = os.path.join(filepath, f"video_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_lowflow.mkv")
        out = cv2.VideoWriter(filename, fourcc, 3, (int(width),int(height)))
        
        currentFrame = 0
        while currentFrame < 15:
            currentFrame += 1
            ret, frame = cap.read()
            
            if ret == True:
                out.write(frame)
                
            else:
                r.set(f"station_{station_id}:record_task:status", "error")
                raise Exception("Stream unreachable!")
            
        out.release()
        
    cap.release()
    r.set(f"station_{station_id}:record_task:status", "success")
    
    return videos_number