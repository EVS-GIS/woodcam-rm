import os
import shutil
import bcrypt
import yaml
import click
import configparser

from urllib.parse import urlparse
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
    
    if os.path.isfile('./ssl_certs/cert.pem') and os.path.isfile('./ssl_certs/privkey.pem'):
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
            'group_wait': '10m',
            'group_interval': '5m',
            'repeat_interval': '6h',
            'receiver': 'woodcamrm-users',
            'routes': [
                    {
                        'match': {'app': 'woodcam-rm'},
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

@click.command("provision-grafana")
@with_appcontext
def provision_grafana():
    
    # Copy provisioning files
    shutil.copytree('./grafana', '/etc/grafana', dirs_exist_ok=True)
    
    # Update config file
    config_grafana = configparser.ConfigParser()
    config_grafana.read('/etc/grafana/grafana.ini')
    
    config_grafana.set('smtp', 'enabled', 'true')
    config_grafana.set('smtp', 'host', dotenv_values()['MAIL_SERVER'])
    config_grafana.set('smtp', 'user', dotenv_values()['MAIL_USERNAME'])
    config_grafana.set('smtp', 'password', dotenv_values()['MAIL_PASSWORD'])
    config_grafana.set('smtp', 'from_address', dotenv_values()['MAIL_DEFAULT_SENDER'])
    
    config_grafana.set('server', 'domain', urlparse(dotenv_values()['GRAFANA_URL']).hostname)
    config_grafana.set('server', 'root_url', dotenv_values()['GRAFANA_URL'])
    config_grafana.set('server', 'enforce_domain', 'true')
    
    if os.path.isfile('./ssl_certs/cert.pem') and os.path.isfile('./ssl_certs/privkey.pem'):

        config_grafana.set('server', 'protocol', 'https')
        config_grafana.set('server', 'cert_file', '/etc/grafana/cert.pem')
        config_grafana.set('server', 'cert_key', '/etc/grafana/privkey.pem')
        
        with open('/etc/grafana/provisioning/datasources/woodcam-rm.yml', 'r') as file:
            datasource_config = yaml.safe_load(file)
        
        datasource_config['datasources'][0]['url'] = "https://prometheus:9090"
        datasource_config['datasources'][0]['jsonData'] = {'tlsSkipVerify': True}
        
        with open('/etc/grafana/provisioning/datasources/woodcam-rm.yml', 'w') as file:
            yaml.dump(datasource_config, file)

        
    with open('/etc/grafana/grafana.ini', 'w') as configfile:
        config_grafana.write(configfile)
     
        
def init_app(app):
    app.cli.add_command(prometheus_update)
    app.cli.add_command(provision_grafana)
