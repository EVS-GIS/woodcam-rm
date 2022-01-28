import psycopg2

import click
from flask import current_app, g
from flask.cli import with_appcontext

from werkzeug.security import generate_password_hash


def get_db():
    if 'db' not in g:
        g.db = psycopg2.connect(dbname=current_app.config['DATABASE_NAME'],
                                user=current_app.config['DATABASE_USER'],
                                password=current_app.config['DATABASE_PASSWORD'],
                                host=current_app.config['DATABASE_SERVER'],
                                port=current_app.config['DATABASE_PORT']
                                )

    return g.db


def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()
        
        
def init_db():
    db = get_db()

    with current_app.open_resource('schema.sql') as f:
        cur = db.cursor()
        cur.execute(f.read().decode('utf8'))
        cur.execute(
            f"INSERT INTO users (username, password, role) VALUES (\
                '{current_app.config['DEFAULT_USER']}', \
                '{generate_password_hash(current_app.config['DEFAULT_PASSWORD'])}', \
                'administrator');"
        )
        cur.execute(
            f"INSERT INTO settings (parameter, value) VALUES \
                ('api_check_sleep', 3600),\
                ('records_check_sleep', 1800);"
        )
        db.commit()
        cur.close()


@click.command('init-db')
@with_appcontext
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo('Initialized the database.')
    
    
def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)