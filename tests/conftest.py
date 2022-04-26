import os

import pytest
from woodcamrm import create_app
from woodcamrm.db import init_db


@pytest.fixture
def app():

    app = create_app({
        'TESTING': True,
        'DATABASE_NAME': 'woodcamrmtesting',
    })

    with app.app_context():
        init_db()

    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


class AuthActions(object):
    def __init__(self, client):
        self._client = client

    def login(self, username=app.config['DEFAULT_USER'], password=app.config['DEFAULT_PASSWORD']):
        return self._client.post(
            '/auth/login',
            data={'username': username, 'password': password}
        )

    def logout(self):
        return self._client.get('/auth/logout')


@pytest.fixture
def auth(client):
    return AuthActions(client)