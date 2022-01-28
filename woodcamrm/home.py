from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort

from woodcamrm.auth import login_required
from woodcamrm.db import get_db

bp = Blueprint('home', __name__)

@bp.route('/')
def index():
    pages = [
        {"name": "Station 1", "url": "/station1"},
        {"name": "Station 2", "url": "/station2"},
    ]
    return render_template('base.html')