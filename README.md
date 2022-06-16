# WoodCam RM
WoodCam Records Manager is a Python web application for managing real-time recordings of flotting wood video surveillance cameras installed by EVS lab (UMR5600). It works to manage cameras connected via a VPN over the mobile network to the server on which WoodCam RM runs. 

WoodCam RM is able to:
- Retrieve the amount of data consumed during the month from a router equipped with an SNMP agent.
- Retrieve the water heights (or flow rates) of monitored rivers via an external API.
- Push recording trigger messages to the cameras via the MQTT protocol, according to the water heights observed.
- Check and store the recordings arrived on the server.

WoodCam RM is built with the Flask Python framework.

# Requirements

* SNMP enabled router
* MQTT enabled cameras
* MQTT broker (example: mosquitto)

# Quick start
```bash
# Clone this repository
git clone https://github.com/EVS-GIS/woodcam-rm.git
cd woodcam-rm

# Create python virtualenv
python -m venv env --prompt woodcam-rm
source env/bin/activate

# Install package and dependencies
python -m pip install -e .

# Customize .env file (see details below)
cp .env.example .env
vi .env 

# Initialize database
flask init-db # Only the first time to seed the first data
flask db upgrade # At each woodcamrm version upgrade

# Run application
flask run
```

## Customizing the .env file
The .env file contains all settings to initialize and run WoodCam RM.

- Set ```FLASK_ENV=production``` for production environment.
- Set ```SECRET_KEY```: a secret key that will be used for securely signing the session cookie and can be used for any other security related needs by extensions or your application. It should be a long random bytes or str.
- Set all the database configuration with your own values (WoodCam RM works with a PostgreSQL database).
- Set the ```API_URL``` with the API from which you retrieve water heights. Warning: using other API that French Hub'Eau will require some modifications in the woodcamrm/jobs.py file.
- Set all the MQTT broker configuration with your own values.
- Set the OIDs to retrieve the received and transmitted data volumes on the router.
- Set a default user and password for the app (will be created at ```flask init-db``` run). 
- Set ```SCHEDULER_TIMEZONE``` with your one.

# Production considerations
## Run prod with gunicorn
```bash
python -m pip install gunicorn
gunicorn -w 1 'woodcamrm:create_app()'
```

Service file /etc/systemd/system/woodcamrm.service
```
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/woodcam-rm
Environment="PATH=/var/www/woodcam-rm/env/bin"
ExecStart=/var/www/woodcam-rm/env/bin/gunicorn --workers 1 --bind 127.0.0.1:8000 'woodcamrm:create_app()'

[Install]
WantedBy=multi-user.target
```

Enable service
```bash
sudo systemctl enable woodcamrm.service
sudo systemctl start woodcamrm.service
```

# Deploy this app and all dependencies using docker-compose

- Copy the example .env file and make the required configuration changes (database, etc...)
- Install docker-compose (https://docs.docker.com/compose/install/)
- Copy prometheus/web.yml.example to prometheus/web.yml
- If you want to use TLS encryption, place your cacert.pem and privatekey.pem in prometheus/.
- Hash a password using https://bcrypt-generator.com/ and copy/paste it to prometheus/web.yml file

```bash
# Run containers
docker-compose up -d

# Create database
docker-compose exec app flask db upgrade # At each woodcamrm version upgrade
docker-compose exec app flask seed-db # Only the first time to seed the default user and the tables

# Restart services
docker-compose restart
```

# Run development tests (testing database needed)

```bash
coverage run -m pytest
```