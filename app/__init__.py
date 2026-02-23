print("🚀 NEW CLEAN BUILD - NO MYSQL")

import os

# Load .env before Config so SMTP, DB, SECRET_KEY etc. are available
from dotenv import load_dotenv
load_dotenv()  # loads from project root (.env)

from flask import Flask
from flask_cors import CORS
from config import Config

def create_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'templates'),
        static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'static')
    )

    app.config.from_object(Config)

    # Mail / SMTP config (from env)
    app.config["MAIL_SERVER"] = os.getenv("SMTP_SERVER")
    app.config["MAIL_PORT"] = int(os.getenv("SMTP_PORT", "587"))
    app.config["MAIL_USERNAME"] = os.getenv("SMTP_USERNAME")
    app.config["MAIL_PASSWORD"] = os.getenv("SMTP_PASSWORD")
    app.config["MAIL_USE_TLS"] = True
    app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER")

    CORS(app)

    # SQLite: point to instance folder and avoid :memory: so the DB file persists
    uri = (app.config.get("SQLALCHEMY_DATABASE_URI") or "").strip()
    if uri.startswith("sqlite"):
        instance_path = app.instance_path
        os.makedirs(instance_path, exist_ok=True)
        db_path = os.path.normpath(os.path.join(instance_path, "local.db"))
        db_uri = "sqlite:///" + db_path.replace("\\", "/")
        if ":memory:" in uri or uri in ("sqlite://", "sqlite:///"):
            app.config["SQLALCHEMY_DATABASE_URI"] = db_uri
        elif "local.db" in uri and not os.path.isabs(uri.replace("sqlite:///", "").strip().split("?")[0]):
            app.config["SQLALCHEMY_DATABASE_URI"] = db_uri

    # Database: Flask-SQLAlchemy only. Import all models so create_all() creates every table (including users).
    from .models.ingestion_models import db, User, ResetOTP  # noqa: F401 - register tables for create_all
    db.init_app(app)
    with app.app_context():
        db.create_all()
        # Optional startup check: ensure DB is reachable
        try:
            from sqlalchemy import text
            db.session.execute(text("SELECT 1"))
            print("✅ Database connection OK")
        except Exception as err:
            print(f"⚠️ Database check failed: {err}")

    # Register blueprints
    from .routes import main
    from .chatbot.financial_chatbot import chatbot_bp
    from .ingestion_routes import ingestion_bp
    from .sms_routes import sms_bp

    app.register_blueprint(main)
    app.register_blueprint(chatbot_bp)
    app.register_blueprint(ingestion_bp)
    app.register_blueprint(sms_bp)

    # CLI: flask seed-user <user_id> — ensure user has synthetic transaction data
    import click
    @app.cli.command("seed-user")
    @click.argument("user_id", type=int)
    def seed_user_cmd(user_id):
        """Ensure the given user has synthetic transaction data (copy in DEMO_MODE or generate new)."""
        from app.utils.seed_user import ensure_user_has_synthetic_data
        action, count = ensure_user_has_synthetic_data(user_id)
        if action == "already_has_data":
            click.echo("User already has transactions.")
        elif action == "copied":
            click.echo("Synthetic data copied to user %s (count=%s)." % (user_id, count))
        else:
            click.echo("Synthetic data generated for user %s (count=%s)." % (user_id, count))

    return app
