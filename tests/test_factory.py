from woodcamrm import create_app
from flask import render_template


def test_config():
    assert not create_app().testing
    assert create_app({'TESTING': True}).testing


# def test_home(client):
#     response = client.get('/')
#     assert response.data == render_template('home/index.html', hometext="Hello, World!")