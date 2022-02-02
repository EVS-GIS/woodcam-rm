import psycopg2
import click

from flask import current_app, g
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash


def get_db():
    if "db" not in g:
        g.db = psycopg2.connect(
            dbname=current_app.config["DATABASE_NAME"],
            user=current_app.config["DATABASE_USER"],
            password=current_app.config["DATABASE_PASSWORD"],
            host=current_app.config["DATABASE_SERVER"],
            port=current_app.config["DATABASE_PORT"],
        )

    return g.db


def close_db(e=None):
    db = g.pop("db", None)

    if db is not None:
        db.close()


def init_db():
    db = get_db()

    with current_app.open_resource("schema.sql") as f:
        cur = db.cursor()
        cur.execute(f.read().decode("utf8"))

        # Insert default values
        cur.execute(
            f"INSERT INTO users (username, password, role) VALUES (\
                '{current_app.config['DEFAULT_USER']}', \
                '{generate_password_hash(current_app.config['DEFAULT_PASSWORD'])}', \
                'administrator');"
        )
        cur.execute(
            "INSERT INTO settings (parameter, value) VALUES \
                ('api_check_sleep', 3600),\
                ('records_check_sleep', 1800), \
                ('ssh_pub_key', ''), \
                ('ssh_priv_key', '');"
        )
        cur.execute(
            "INSERT INTO jobs (job_name, priority, full_name, description) VALUES \
                ('alive_check', 10, 'Alive check', 'Check if all jobs and cameras are running correctly and send mail notifications if needed.'), \
                ('hydrodata_update', 20, 'Update hydro metrics', 'Update hydro metrics with external API and trigger recording if needed.'), \
                ('records_check', 40, 'Check records', 'Check records received from camera.'), \
                ('download_records', 50, 'Download records', 'Download missing records after a service interruption.'), \
                ('check_data_plan', 30, 'Check data plan', 'Estimate 4G data plan state.');"
        )
        db.commit()
        cur.close()


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Clear the existing data and create new tables."""

    confirmation = input(
        "Warning: this irreversible action will completely reset any existing WoodCamRM database. Are you sure? [y/N]"
    )
    if confirmation.lower() in ["y", "yes"]:
        init_db()
        click.echo("Initialized the database.")
    else:
        click.echo("Aborted")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
