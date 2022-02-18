import os
from dotenv import dotenv_values

from flask import Flask
from woodcamrm.extensions import mqtt, dbsql, scheduler

from woodcamrm.db import Stations


def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(dotenv_values())
    app.config['MQTT_BROKER_PORT'] = int(app.config['MQTT_BROKER_PORT'])
    app.config['MQTT_TLS_ENABLED'] = False
    
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
        stations = Stations.query.all()

    # APScheluder for CRON jobs
    scheduler.api_enabled = False
    scheduler.init_app(app)

    with app.app_context():
        from . import jobs 
        app.register_blueprint(jobs.bp)

        scheduler.start()
        
    # MQTT client
    from . import mqtt_client
    mqtt.init_app(app)
        
    @mqtt.on_connect()
    def handle_connect(client, userdata, flags, rc):
        with app.app_context():
            stations = Stations.query.all()
            if stations:
                mqtt_client.subscribe_topics(stations)
                    
    @mqtt.on_message()
    def handle_mqtt_message(client, userdata, message):
        with app.app_context():
            stations = Stations.query.all()
            mqtt_data = mqtt_client.to_dict(stations, message)
            
            setattr(mqtt_data['station'], mqtt_data['topic'], mqtt_data['data'])
            dbsql.session.commit()
            

    # List all stations for sidebar
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
