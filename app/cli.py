import click
from werkzeug.security import generate_password_hash

from .db import get_db


@click.command("create-admin")
@click.option("--name", prompt="Full name")
@click.option("--email", prompt="Email")
@click.password_option()
def create_admin(name, email, password):
    """Create an admin account (admins cannot register through the website)."""
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            click.echo("That email is already registered.")
            return
        cur.execute(
            "INSERT INTO users (full_name, email, password_hash, role) "
            "VALUES (%s, %s, %s, 'admin')",
            (name, email, generate_password_hash(password)),
        )
    conn.commit()
    click.echo(f"Admin account created for {email}.")
