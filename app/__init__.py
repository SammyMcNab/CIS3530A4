from flask import Flask
import os
import psycopg2

SECRET_KEY = os.getenv("FLASK_SECRET_KEY") or os.urandom(24).hex()

def create_app():
    app = Flask(__name__)
    app.secret_key = SECRET_KEY

    # Import and register routes
    from app.routes import main
    app.register_blueprint(main)

    return app
