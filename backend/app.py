"""
Stock Analysis Web Application - Flask Backend
Author: Jaber Kaal | GCU MSSE Capstone
"""

from flask import Flask
from flask_cors import CORS
from routes.analysis import analysis_bp
from routes.validate import validate_bp
from routes.predict import predict_bp
import logging
import os

def create_app():
    app = Flask(__name__)
    CORS(app)

    # Logging setup (FR-8 / US-7)
    log_level = os.getenv("LOG_LEVEL", "INFO")
    os.makedirs("logs", exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler("logs/app.log"),
            logging.StreamHandler()
        ]
    )

    # Register blueprints
    app.register_blueprint(validate_bp, url_prefix="/api/v1")
    app.register_blueprint(analysis_bp, url_prefix="/api/v1")
    app.register_blueprint(predict_bp,  url_prefix="/api/v1")

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)

# Module-level app for gunicorn
app = create_app()
