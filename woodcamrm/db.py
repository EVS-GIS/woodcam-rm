import enum
import click

from flask import current_app
from flask.cli import with_appcontext

from sqlalchemy.sql import func

from werkzeug.security import generate_password_hash

from woodcamrm.extensions import dbsql


class Role(enum.Enum):
    admin = "Administrator"
    viewer = "Viewer"
    

class JobState(enum.Enum):
    running = 'Running' 
    warn = "Warning"
    error = 'Error'
    stopped = 'Stopped'
    

class RecordMode(enum.Enum):
    high = "High flow" 
    low = "Low flow"
    no = "Not recording"
    

class SetupMode(enum.Enum):
    monitoring = "Monitoring only" 
    mqtt = "MQTT messages"
    rtsp = "RTSP stream"
    
    
class Users(dbsql.Model):
    id = dbsql.Column(dbsql.Integer, primary_key=True)
    username = dbsql.Column(dbsql.String(80), unique=True, nullable=False)
    password = dbsql.Column(dbsql.String(120), nullable=False)
    role = dbsql.Column(dbsql.Enum(Role), nullable=False, default='viewer')
    email = dbsql.Column(dbsql.String(120), unique=True)
    notify = dbsql.Column(dbsql.Boolean, nullable=False, default=False)

    def __repr__(self):
        return '<User %r>' % self.username


class Stations(dbsql.Model):
    id = dbsql.Column(dbsql.Integer, primary_key=True)
    common_name = dbsql.Column(dbsql.String(120), unique=True, nullable=False)
    created = dbsql.Column(dbsql.DateTime, nullable=False, default=func.now())
    setup_mode = dbsql.Column(dbsql.Enum(SetupMode), nullable=False, default="monitoring")
    api_name = dbsql.Column(dbsql.String(120))
    monthly_data = dbsql.Column(dbsql.Integer)
    current_data = dbsql.Column(dbsql.Numeric)
    last_data_check = dbsql.Column(dbsql.DateTime)
    reset_day = dbsql.Column(dbsql.Integer)
    phone_number = dbsql.Column(dbsql.String(120))
    ip = dbsql.Column(dbsql.String(120))
    camera_port = dbsql.Column(dbsql.Integer)
    installation_port = dbsql.Column(dbsql.Integer)
    mqtt_prefix = dbsql.Column(dbsql.String(120))
    snmp_received = dbsql.Column(dbsql.String(120))
    snmp_transmitted = dbsql.Column(dbsql.String(120))
    last_ping = dbsql.Column(dbsql.DateTime)
    ping_alert = dbsql.Column(dbsql.Boolean, nullable=False, default=False)
    last_hydro_time = dbsql.Column(dbsql.DateTime)
    last_hydro = dbsql.Column(dbsql.Numeric)
    current_recording = dbsql.Column(dbsql.Enum(RecordMode), default="no")
    last_record_change = dbsql.Column(dbsql.DateTime, default=func.now())
    current_daymode = dbsql.Column(dbsql.Integer)
    temp_alert = dbsql.Column(dbsql.Integer, nullable=False, default=0)
    sd_alert = dbsql.Column(dbsql.Integer, nullable=False, default=0)
    sd_disruption = dbsql.Column(dbsql.Integer, nullable=False, default=0)
    tampering = dbsql.Column(dbsql.Integer, nullable=False, default=0)
    jan_threshold = dbsql.Column(dbsql.Numeric)
    feb_threshold = dbsql.Column(dbsql.Numeric)
    mar_threshold = dbsql.Column(dbsql.Numeric)
    apr_threshold = dbsql.Column(dbsql.Numeric)
    may_threshold = dbsql.Column(dbsql.Numeric)
    jun_threshold = dbsql.Column(dbsql.Numeric)
    jul_threshold = dbsql.Column(dbsql.Numeric)
    aug_threshold = dbsql.Column(dbsql.Numeric)
    sep_threshold = dbsql.Column(dbsql.Numeric)
    oct_threshold = dbsql.Column(dbsql.Numeric)
    nov_threshold = dbsql.Column(dbsql.Numeric)
    dec_threshold = dbsql.Column(dbsql.Numeric)
    
    def __repr__(self):
        return '<Station %r>' % self.common_name
    
    
class Jobs(dbsql.Model):
    id = dbsql.Column(dbsql.Integer, primary_key=True)
    job_name = dbsql.Column(dbsql.String, unique=True, nullable=False)
    full_name = dbsql.Column(dbsql.String, nullable=False)
    description = dbsql.Column(dbsql.String)
    last_execution = dbsql.Column(dbsql.DateTime)
    state = dbsql.Column(dbsql.Enum(JobState), nullable=False, default='warn')
    message = dbsql.Column(dbsql.String)
    
    def __repr__(self):
        return '<Job %r>' % self.job_name


class Settings(dbsql.Model):
    id = dbsql.Column(dbsql.Integer, primary_key=True)
    parameter = dbsql.Column(dbsql.String, unique=True, nullable=False)
    value = dbsql.Column(dbsql.String, nullable=False)
    
    def __repr__(self):
        return '<Job %r>' % self.parameter
    

def init_db():
    dbsql.drop_all()
    dbsql.create_all()
    
    default_user = Users(username=current_app.config['DEFAULT_USER'], 
                        password=generate_password_hash(current_app.config['DEFAULT_PASSWORD']),
                        role='admin',
                        email=current_app.config['DEFAULT_EMAIL'],
                        notify=True)
    alive_check = Jobs(job_name = 'alive_check',
                       full_name = 'Alive check',
                       description = 'Check if all cameras are reachable and send mail notifications if not. Run data recovery after a service interruption.')
    hydrodata_update = Jobs(job_name = 'hydrodata_update',
                       full_name = 'Update hydro metrics',
                       description = 'Update hydro metrics with external API and trigger recording if needed.')    
    records_check = Jobs(job_name = 'records_check',
                       full_name = 'Check records',
                       description = 'Check and classify records received from camera.')
    download_records = Jobs(job_name = 'download_records',
                       full_name = 'Download records',
                       description = 'Download missing records after a service interruption.')
    check_data_plan = Jobs(job_name = 'check_data_plan',
                       full_name = 'Check data plan',
                       description = 'Estimate 4G data plan usage.')
    
    dbsql.session.add(default_user)
    dbsql.session.add(alive_check)
    dbsql.session.add(hydrodata_update)
    dbsql.session.add(records_check)
    dbsql.session.add(download_records)
    dbsql.session.add(check_data_plan)
    
    if current_app.config['DEBUG']:
        test_mqtt = Stations(common_name='Bureau MQTT',
                            api_name='V2942010',
                            setup_mode='mqtt',
                            monthly_data=10000,
                            reset_day=4,
                            ip='10.8.0.2',
                            mqtt_prefix='camera/bureau')
        test_rtsp = Stations(common_name='Chazey RTSP',
                            api_name='V2942010',
                            setup_mode='rtsp',
                            ip='193.252.53.58') 
        test_monitoring = Stations(common_name='Bureau monitoring',
                            api_name='V2942010',
                            setup_mode='monitoring',
                            monthly_data=10000,
                            reset_day=4,
                            ip='10.8.0.2',
                            mqtt_prefix='camera/bureau')               
        dbsql.session.add(test_mqtt)
        dbsql.session.add(test_rtsp)
        dbsql.session.add(test_monitoring)
        
    dbsql.session.commit()


@click.command("init-db")
@click.option("--yes", "-y", is_flag=True, help="Don't ask for confirmation.")
@with_appcontext
def init_db_command(yes):
    """Clear the existing data and create new tables."""

    if yes:
        confirmation = "yes"
    else:
        confirmation = input(
            "Warning: this irreversible action will completely reset any existing WoodCamRM database. Are you sure? [y/N]"
        )
        
    if confirmation.lower() in ["y", "yes"]:
        init_db()
        click.echo("Initialized the database.")
    else:
        click.echo("Aborted")
        

def init_app(app):
    app.cli.add_command(init_db_command)
    