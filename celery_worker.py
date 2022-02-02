import os
from woodcamrm import celery, create_app, daemons

app = create_app(os.getenv('FLASK_CONFIG') or None)
app.app_context().push()