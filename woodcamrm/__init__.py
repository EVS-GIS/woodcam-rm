import os
import cv2
import time
import redis
import shutil

from datetime import datetime
from dotenv import dotenv_values

from flask import Flask, Blueprint
from flask_restx import Api

from sqlalchemy import exc

from celery import Celery
from celery.utils.log import get_task_logger

from woodcamrm.extensions import dbsql, scheduler, mail, migrate
from woodcamrm.db import Stations


celery = Celery(__name__, 
                backend=dotenv_values()["CELERY_RESULT_BACKEND"],
                broker=dotenv_values()["CELERY_BROKER_URL"])
api_bp = Blueprint('api', __name__)
api = Api(api_bp, version=1.0, title='WoodCam-RM API', description='WoodCam-RM backend API')


def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(dotenv_values())
    
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
    migrate.init_app(app, dbsql)

    with app.app_context():
        try:
            stations = Stations.query.all()                
        except exc.ProgrammingError:
            stations = []
            print('The database needs to be updated. Please run flask init-db first.')
    
    # Mailing system
    mail.init_app(app)
    
    # API    
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    from . import api_endpoints
    
    # APScheluder and Celery for CRON jobs
    scheduler.api_enabled = False
    scheduler.init_app(app)   
        
    with app.app_context():
        from . import jobs
        app.register_blueprint(jobs.bp)
        scheduler.start()
        
        celery.conf.update(app.config)

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
    
    # CLI commands
    from . import cli
    cli.init_app(app)

    return app


#####
# Celery task definition below
####

logger = get_task_logger(__name__)

@celery.task()
def save_video_file(filepath, rtsp_url, station_id):
    
    r = redis.from_url(dotenv_values()["CELERY_BROKER_URL"])
    recording_mode = r.get(f"station_{station_id}:record_mode")
    
    logger.debug(f"task for station {station_id} in {recording_mode} recording mode")
    
    if recording_mode == b'no':
        return 0
    
    r.set(f"station_{station_id}:record_task:status", "started")
    
    if not os.path.isdir(filepath):
        os.mkdir(filepath)
        
    if not os.path.isdir(os.path.join(filepath, "archives")):
        os.mkdir(os.path.join(filepath, "archives"))
        
    logger.debug(f"opening {rtsp_url} video capture")
    cap = cv2.VideoCapture(rtsp_url)
    
    # Get current width of frame
    width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    # Get current height of frame
    height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)

    # Define the codec and create VideoWriter object
    fourcc = cv2.VideoWriter_fourcc(*'MJPG')
    
    videos_number = 0
    
    while recording_mode == b"high":
        recording_mode = r.get(f"station_{station_id}:record_mode")
        
        # Update redis data
        r.set(f"station_{station_id}:last_record", time.time())
        r.set(f"station_{station_id}:record_task:status", "recording")
        
        # Define output
        archive_file = os.path.join(filepath, "archives", f"archive_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.avi")
        archive_output = cv2.VideoWriter(archive_file, fourcc, 3, (int(width),int(height)))
        
        archive_timeout = time.time() + 600
        logger.debug(f"starting {archive_file} recording")
        logger.debug(f"archive file timeout: {datetime.fromtimestamp(archive_timeout).strftime('%Y-%m-%d %H:%M:%S')}")
        while time.time() < archive_timeout:
            videos_number+=1
            
            live_file = os.path.join(filepath, f"video_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.avi")
            live_output = cv2.VideoWriter(live_file, fourcc, 3, (int(width),int(height)))
            
            live_timeout = time.time() + 60
            logger.debug(f"starting {live_file} recording")
            logger.debug(f"live file timeout: {datetime.fromtimestamp(live_timeout).strftime('%Y-%m-%d %H:%M:%S')}")
            
            while time.time() < live_timeout:
                ret, frame = cap.read()
                
                if ret == True:
                    live_output.write(frame)
                    archive_output.write(frame)
                    
                else:
                    r.set(f"station_{station_id}:record_task:status", "warning")
                    logger.warning('stream unreachable: trying to restart video capture')
                    
                    try:
                        cap.release()
                        cap = cv2.VideoCapture(rtsp_url)
                    except:
                        live_output.release()
                        archive_output.release()
                        raise Exception("Unable to re-open stream!")
            
            logger.debug(f"release {live_file}")
            live_output.release()
            r.set(f"station_{station_id}:last_record", time.time())
        
        logger.debug(f"release {archive_file}")
        archive_output.release()
    
    
    if recording_mode == b"low":
        videos_number+=1
        r.set(f"station_{station_id}:last_record", time.time())
        r.set(f"station_{station_id}:record_task:status", "recording")
        
        # Define output
        live_file = os.path.join(filepath, f"video_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.avi")
        archive_file = os.path.join(filepath, "archives", f"archive_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.avi")
        live_output = cv2.VideoWriter(live_file, fourcc, 3, (int(width),int(height)))
        
        live_timeout = time.time() + 30
        logger.debug(f"starting {live_file} recording")
        logger.debug(f"archive file timeout: {datetime.fromtimestamp(live_timeout).strftime('%Y-%m-%d %H:%M:%S')}")
        while time.time() < live_timeout:
            ret, frame = cap.read()
            
            if ret == True:
                live_output.write(frame)
                
            else:
                r.set(f"station_{station_id}:record_task:status", "warning")
                logger.warning('stream unreachable: trying to restart video capture')
                
                try:
                    cap.release()
                    cap = cv2.VideoCapture(rtsp_url)
                except:
                    live_output.release()
                    raise Exception("Unable to re-open stream!")
            
        logger.debug(f"release {live_file}")
        live_output.release()
        shutil.copyfile(live_file, archive_file)
        
    logger.debug(f"release video capture")
    cap.release()
    r.set(f"station_{station_id}:record_task:status", "success")
    
    return videos_number