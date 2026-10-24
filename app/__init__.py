from flask import Flask, render_template

from config import Config

from . import db
from .cli import create_admin
from .extensions import csrf, mail


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    csrf.init_app(app)
    mail.init_app(app)
    db.init_app(app)
    app.cli.add_command(create_admin)

    from .admin.routes import admin_bp
    from .auth.routes import auth_bp
    from .client.routes import client_bp
    from .main.routes import main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(client_bp, url_prefix="/client")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # Friendly error pages instead of stack traces
    for code, message in (
        (403, "You do not have permission to open this page."),
        (404, "We could not find that page."),
        (500, "Something went wrong on our side. Please try again."),
    ):
        app.register_error_handler(
            code,
            lambda e, code=code, message=message: (
                render_template("error.html", code=code, message=message),
                code,
            ),
        )

    return app
