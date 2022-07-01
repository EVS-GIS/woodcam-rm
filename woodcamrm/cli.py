import os
import shutil
import bcrypt
import yaml
import click

from flask.cli import with_appcontext
from dotenv import dotenv_values

@click.command("prometheus-update")
@with_appcontext
def prometheus_update():
    
    # Copy default files
    shutil.copytree('./prometheus', '/etc/prometheus', dirs_exist_ok=True)
    
    # Create prometheus web configuration file  
    user = dotenv_values()['DEFAULT_USER']
    password = dotenv_values()['DEFAULT_PASSWORD']
    hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    web_conf = {'basic_auth_users': {user: hashed_password.decode()}}
    
    if os.path.isfile('./prometheus/cert.pem') and os.path.isfile('./prometheus/privkey.pem'):
        web_conf['tls_server_config'] = {
            'cert_file': '/etc/prometheus/cert.pem',
            'key_file': '/etc/prometheus/privkey.pem'
            }
    
    with open('/etc/prometheus/web.yml', 'w') as file:
        yaml.dump(web_conf, file)
    
    # Create alertmanager configuration file          
    alertm_conf = {
        'global': {
            'smtp_from': dotenv_values()['MAIL_DEFAULT_SENDER'],
            'smtp_smarthost': f"{dotenv_values()['MAIL_SERVER']}:{dotenv_values()['MAIL_PORT']}",
            'smtp_auth_username': dotenv_values()['MAIL_USERNAME'],
            'smtp_auth_password': dotenv_values()['MAIL_PASSWORD'],
            'smtp_require_tls': bool(dotenv_values()['MAIL_USE_TLS'])
            },
        'route': {
            'group_by': ['severity'],
            'group_wait': '30s',
            'group_interval': '5m',
            'repeat_interval': '6h',
            'receiver': 'woodcamrm-users',
            'routes': [
                    {
                        'match': {'app': 'woodcam-rm'},
                        'continue': True
                    },
                    {
                        'match': {'alertname': 'ConnectionUnstable'},
                        'mute_time_intervals': ['gateways-reboot']
                    }
                ]
            },
        'receivers': [{
            'name': 'woodcamrm-users',
            'email_configs': [{'to': dotenv_values()['DEFAULT_EMAIL']}]
        }],
        'time_intervals': [{
            'name': 'gateways-reboot',
            'time_intervals': [{
                'times': [{
                    'start_time': '00:00',
                    'end_time': '00:30'
                }]
                }]
            }]
    }
    
    with open('/etc/prometheus/alertmanager.yml', 'w') as file:
        yaml.dump(alertm_conf, file)
        
        
def init_app(app):
    app.cli.add_command(prometheus_update)