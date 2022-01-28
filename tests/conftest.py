import os

import pytest
from woodcamrm import create_app
from woodcamrm.db import get_db, init_db

with open(os.path.join(os.path.dirname(__file__), 'data.sql'), 'rb') as f:
    _data_sql = f.read().decode('utf8')


@pytest.fixture
def app():

    app = create_app({
        'TESTING': True,
        'DATABASE_NAME': 'woodcamrmtesting',
    })

    with app.app_context():
        init_db()
        db = get_db()
        cur = db.cursor()
        cur.execute(_data_sql)
        cur.close()
        db.commit()

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

    def login(self, username='test', password='test'):
        return self._client.post(
            '/auth/login',
            data={'username': username, 'password': password}
        )

    def logout(self):
        return self._client.get('/auth/logout')


@pytest.fixture
def auth(client):
    return AuthActions(client)