import os

from setuptools import find_packages, setup
from setuptools.command.install import install
from setuptools.command.develop import develop


def post_install_script():
    # Create prometheus web configuration file
    import bcrypt
    import yaml
    from dotenv import load_dotenv
    
    load_dotenv()
    
    user = os.environ['DEFAULT_USER']
    password = os.environ['DEFAULT_PASSWORD']
    hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    web_conf = {'basic_auth_users': {user: hashed_password.decode()}}
    
    if os.path.isfile('./prometheus/cert.pem') and os.path.isfile('./prometheus/privkey.pem'):
        web_conf['tls_server_config'] = {
            'cert_file': '/etc/prometheus/cert.pem',
            'key_file': '/etc/prometheus/privkey.pem'
            }
    
    with open('./prometheus/web.yml', 'w') as file:
        yaml.dump(web_conf, file)
    
    # Create alertmanager configuration file          
    alertm_conf = {
        'global': {
            'smtp_from': os.environ['MAIL_DEFAULT_SENDER'],
            'smtp_smarthost': f"{os.environ['MAIL_SERVER']}:{os.environ['MAIL_PORT']}",
            'smtp_auth_username': os.environ['MAIL_USERNAME'],
            'smtp_auth_password': os.environ['MAIL_PASSWORD'],
            'smtp_require_tls': bool(os.environ['MAIL_USE_TLS'])
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
            'email_configs': [{'to': os.environ['DEFAULT_EMAIL']}]
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
    
    with open('./prometheus/alertmanager.yml', 'w') as file:
        yaml.dump(alertm_conf, file)


class PostInstall(install):
    def run(self):
        install.run(self)
        post_install_script()
        
        
class PostDevelop(develop):
    def run(self):
        develop.run(self)
        post_install_script()
            

setup(
    name='woodcamrm',
    version='1.0.1',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    cmdclass={
        'install': PostInstall,
        'develop': PostDevelop
    },
    install_requires=[
        'flask',
        'flask-restx',
        'flask-sqlalchemy',
        'flask-apscheduler',
        'flask-mail',
        'flask-wtf',
        'flask-migrate',
        'psycopg2-binary',
        'requests',
        'python-dotenv',
        'pysnmp',
        'geoalchemy2',
        'suntime',
        'celery[redis]',
        'opencv-python-headless',
        'pyyaml',
        'bcrypt'
    ],
)
