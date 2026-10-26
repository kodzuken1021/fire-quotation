import click

from .models.user import Admin, User


@click.command("create-admin")
@click.option("--name", prompt="Full name")
@click.option("--email", prompt="Email")
@click.password_option()
def create_admin(name, email, password):
    """Create an admin account (admins cannot register through the website)."""
    email = email.strip().lower()
    if User.email_exists(email):
        click.echo("That email is already registered.")
        return
    admin = Admin(name.strip(), email)
    admin.set_password(password)
    admin.save()
    click.echo(f"Admin account created for {email}.")
