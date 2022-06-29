import os

from setuptools import find_packages, setup
from setuptools.command.develop import develop

class PostInstall(develop):
    def run(self):
        develop.run(self)
        
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
                }
            }
        
        with open('./prometheus/alertmanager.yml', 'w') as file:
            yaml.dump(alertm_conf, file)
            

setup(
    name='woodcamrm',
    version='1.0.1',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    cmdclass={
        'develop': PostInstall
    },
    install_requires=[
        'flask',
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
