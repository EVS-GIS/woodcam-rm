import os
from sqlite3 import ProgrammingError

from dotenv import dotenv_values

from flask import Flask

from sqlalchemy import exc

from celery import Celery

from woodcamrm.extensions import mqtt, dbsql, scheduler, mail
from woodcamrm.db import Stations, SetupMode
from woodcamrm.rtsp import update_rtsp_proxies


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
            stations = Stations.query.filter_by(setup_mode=SetupMode.mqtt).all()
            if stations:
                mqtt_client.subscribe_topics(stations)

    @mqtt.on_message()
    def handle_mqtt_message(client, userdata, message):
        with app.app_context():
            stations = Stations.query.filter_by(setup_mode=SetupMode.mqtt).all()
            mqtt_data = mqtt_client.to_dict(stations, message)

            setattr(mqtt_data['station'],
                    mqtt_data['topic'], mqtt_data['data'])
                
            dbsql.session.commit()
            
            # Mail alerts
            mqtt_client.alerts(stations)

    # List all stations for sidebar

    @app.context_processor
    def inject_pages():
        return dict(pages=stations)
    
    # Check RTSP configs
    with app.app_context():
        try:
            stations_rtsp = Stations.query.filter_by(setup_mode=SetupMode.rtsp).all()
            if stations_rtsp:
                update_rtsp_proxies(stations_rtsp, app.config['RTSP_SERVER_URL'], app.config['RTSP_SERVER_API_PORT'])
        except exc.ProgrammingError:
            pass
        
    from . import auth

    app.register_blueprint(auth.bp)

    from . import station

    app.register_blueprint(station.bp)

    from . import home

    app.register_blueprint(home.bp)
    app.add_url_rule("/", endpoint="index")

    return app
