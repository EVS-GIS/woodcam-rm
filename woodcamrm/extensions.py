from flask_sqlalchemy import SQLAlchemy
from flask_apscheduler import APScheduler
from flask_mqtt import Mqtt
from flask_mail import Mail
from flask_login import LoginManager

dbsql = SQLAlchemy()
scheduler = APScheduler()
mqtt = Mqtt()
mail = Mail()
login_manager = LoginManager()