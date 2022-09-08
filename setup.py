import os

from setuptools import find_packages, setup
            

setup(
    name='woodcamrm',
    version='1.0.1',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'bcrypt==3.2.2',
        'celery[redis]==5.2.7',
        'flask==2.1.2',
        'flask_httpauth==4.7.0',
        'flask-restx==0.5.1',
        'flask-sqlalchemy==2.5.1',
        'flask-apscheduler==1.12.4',
        'flask-mail==0.9.1',
        'flask-wtf==1.0.1',
        'flask-migrate==3.1.0',
        'geoalchemy2==0.12.1',
        'psycopg2-binary==2.9.3',
        'pysnmp==4.4.12',
        'python-dotenv==0.20.0',
        'pyyaml==6.0',
        'requests==2.28.1',
        'simplejson==3.17.6',
        'suntime==1.2.5',
        'werkzeug==2.1.2'
    ],
)
