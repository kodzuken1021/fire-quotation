from flask import Flask, render_template
from flask_wtf.csrf import CSRFError

from config import Config

from . import db
from .cli import create_admin
from .extensions import csrf, mail

# Where the browser may load things from (Bootstrap, Google Fonts, Cloudflare DNS check)
CSP = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.jsdelivr.net; "
    "style-src 'self' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com https://cdn.jsdelivr.net; "
    "img-src 'self' data:; "
    "connect-src 'self' https://cloudflare-dns.com; "
    "frame-ancestors 'none'; form-action 'self'; base-uri 'self'"
)


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
        (400, "Your form expired or was invalid. Go back, refresh the page and try again."),
        (403, "You do not have permission to open this page."),
        (404, "We could not find that page."),
        (405, "That action is not allowed here."),
        (500, "Something went wrong on our side. Please try again."),
        (413, "That file is too large. The maximum size is 2 MB."),
    ):
        app.register_error_handler(
            code,
            lambda e, code=code, message=message: (
                render_template("error.html", code=code, message=message),
                code,
            ),
        )
    app.register_error_handler(CSRFError, lambda e: (
        render_template("error.html", code=400,
                        message="Your form expired or was invalid. Go back, refresh the page and try again."),
        400,
    ))

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Content-Security-Policy", CSP)
        return response

    return app