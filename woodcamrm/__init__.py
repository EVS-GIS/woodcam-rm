import os
from psycopg2.extras import RealDictCursor
from dotenv import dotenv_values

from flask import Flask
from .extensions import scheduler


def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(dotenv_values())

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

    from . import db

    db.init_app(app)

    # APScheluder for CRON jobs
    scheduler.api_enabled = False
    scheduler.init_app(app)

    with app.app_context():
        from . import jobs 
        app.register_blueprint(jobs.bp)

        scheduler.start()

    # List all stations for sidebar
    @app.context_processor
    def inject_pages():
        database = db.get_db()
        cur = database.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id, common_name FROM stations;")
        stations = cur.fetchall()
        cur.close()

        return dict(pages=stations)

    from . import auth

    app.register_blueprint(auth.bp)

    from . import station

    app.register_blueprint(station.bp)

    from . import home

    app.register_blueprint(home.bp)
    app.add_url_rule("/", endpoint="index")

    return app
