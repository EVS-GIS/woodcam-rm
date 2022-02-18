from flask_sqlalchemy import SQLAlchemy
from flask_apscheduler import APScheduler
from flask_mqtt import Mqtt

dbsql = SQLAlchemy()
scheduler = APScheduler()
mqtt = Mqtt()