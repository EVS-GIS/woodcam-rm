from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_apscheduler import APScheduler
from flask_mqtt import Mqtt
from flask_mail import Mail

dbsql = SQLAlchemy()
scheduler = APScheduler()
mqtt = Mqtt()
mail = Mail()
migrate = Migrate()