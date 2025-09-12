import os
from flask import Flask
from flask_cors import CORS
import mysql.connector
from config import Config

def create_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'templates'),
        static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'static')
    )

    app.config.from_object(Config)
    CORS(app)

    # Attach MySQL connection with error handling
    try:
        app.mysql = mysql.connector.connect(
            host=app.config["MYSQL_HOST"],
            user=app.config["MYSQL_USER"],
            password=app.config["MYSQL_PASSWORD"],
            database=app.config["MYSQL_DB"],
            autocommit=True  # optional but useful
        )
        print("✅ Database connected successfully")
    except mysql.connector.Error as err:
        print(f"⚠️ Database connection failed: {err}")
        print("📝 The app will run without database functionality")
        app.mysql = None

    # Register blueprints
    from .routes import main
    from .chatbot.financial_chatbot import chatbot_bp  # Using integrated financial chatbot

    app.register_blueprint(main)
    app.register_blueprint(chatbot_bp)

    return app
