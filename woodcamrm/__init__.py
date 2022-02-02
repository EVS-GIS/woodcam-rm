import os
from psycopg2.extras import RealDictCursor

from flask import Flask
from .extensions import scheduler
from celery import Celery


celery = Celery(
    __name__, broker="redis://127.0.0.1:6379", backend="redis://127.0.0.1:6379"
)


def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        DATABASE_SERVER=os.environ.get("DATABASE_SERVER"),
        DATABASE_PORT=os.environ.get("DATABASE_PORT"),
        DATABASE_NAME=os.environ.get("DATABASE_NAME"),
        DATABASE_USER=os.environ.get("DATABASE_USER"),
        DATABASE_PASSWORD=os.environ.get("DATABASE_PASSWORD"),
        DEFAULT_USER=os.environ.get("DEFAULT_USER"),
        DEFAULT_PASSWORD=os.environ.get("DEFAULT_PASSWORD"),
        SCHEDULER_TIMEZONE=os.environ.get("TIMEZONE"),
        API_URI=os.environ.get("API_URI"),
        API_STATION_ID=os.environ.get("API_STATION_ID"),
        API_OBSERVATION=os.environ.get("API_OBSERVATION"),
    )

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

    # Celery for daemon processes
    celery.conf.update(app.config)

    # APScheluder for CRON jobs
    scheduler.api_enabled = False
    scheduler.init_app(app)

    with app.app_context():
        from . import jobs  # noqa: F401

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
