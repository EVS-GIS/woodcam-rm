from setuptools import find_packages, setup

setup(
    name='woodcamrm',
    version='1.0.0',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'flask',
        'flask-sqlalchemy',
        'flask-apscheduler',
        'flask-mqtt',
        'flask-mail',
        'flask-wtf',
        'psycopg2-binary',
        'requests',
        'python-dotenv',
        'pysnmp',
        'geoalchemy2',
        'suntime',
        'celery[redis]',
        #'opencv-python'
    ],
)
