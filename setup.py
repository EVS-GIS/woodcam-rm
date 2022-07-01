import os

from setuptools import find_packages, setup
            

setup(
    name='woodcamrm',
    version='1.0.1',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
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
