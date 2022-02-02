# WoodCam RM
WoodCam Records Manager

# Requirements

* snmp
* mqtt broker (eg. mosquitto)

# Quick start

    # Create python virtualenv
    python -m venv env --prompt woodcam-rm
    source env/bin/activate

    # Install dependencies
    python -m pip install -r requirements.txt

    # Customize .env file
    cp .env.example .env
    vi .env 

    # Initialize database
    flask init-db

    # Run application
    flask run

# Deploy this app using docker

- Copy the example .env file and make the required configuration changes in the .env file (database, etc...)
- Build image

        docker build -t my-woodcam-rm:$(git rev-parse --short HEAD) .

- If the database is a new empty instance, initialize it

        docker run -it --rm my-woodcam-rm:$(git rev-parse --short HEAD) flask init-db

- Run a container and access the application at localhost:5050 (customize ports for production environment)

        docker run -it --rm -p 5050:5000 --name my-woodcam-rm-instance my-woodcam-rm:$(git rev-parse --short HEAD)

# Run development tests (testing database needed)

    coverage run -m pytest