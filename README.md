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
flask init-db

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

# Deploy this app using docker

- Copy the example .env file and make the required configuration changes (database, etc...)

```bash
# Build image
docker build -t my-woodcam-rm:$(git rev-parse --short HEAD) .

# If the database is a new empty instance, initialize it
docker run -it --rm my-woodcam-rm:$(git rev-parse --short HEAD) flask init-db

# Run a container and access the application at localhost:5050 (customize ports for production environment)
docker run -it --rm -p 5050:5000 --name my-woodcam-rm-instance my-woodcam-rm:$(git rev-parse --short HEAD)
```

# Run development tests (testing database needed)

```bash
coverage run -m pytest
```