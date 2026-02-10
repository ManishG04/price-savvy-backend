"""
Price Savvy Backend - Flask Application Factory
As per PRD: Flask with Blueprints for modular structure
"""

import os
import logging
from flask import Flask, send_from_directory
from app.config import Config


def configure_logging(app: Flask) -> None:
    """Configure structured logging as per PRD requirements."""
    log_level = logging.DEBUG if app.debug else logging.INFO

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Set Flask's logger
    app.logger.setLevel(log_level)

    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


def create_app(config_class=Config):
    """Application factory pattern for creating Flask app instances."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Configure logging
    configure_logging(app)

    # Enable CORS for frontend
    @app.after_request
    def add_cors_headers(response):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        return response

    # Register blueprints
    from app.api import api_bp

    app.register_blueprint(api_bp, url_prefix="/api/v1")

    # Register error handlers
    from app.errors import register_error_handlers

    register_error_handlers(app)

    # Serve frontend static files
    frontend_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend')
    
    @app.route('/dashboard')
    @app.route('/dashboard/')
    def serve_dashboard():
        return send_from_directory(frontend_folder, 'index.html')

    # Health check route (PRD: lightweight health endpoint)
    @app.route("/health")
    def health_check():
        return {
            "status": "healthy",
            "service": "price-savvy-backend",
            "version": "0.1.0",
        }

    # Root route for API info
    @app.route("/")
    def index():
        return {
            "service": "Price Savvy Backend API",
            "version": "0.1.0",
            "description": "Product price comparison and tracking API",
            "dashboard": "/dashboard",
            "endpoints": {
                "health": "/health",
                "search": "/api/v1/search?q={query}",
                "compare": "/api/v1/compare?ids={id1,id2}",
                "product_by_id": "/api/v1/products/{id}",
                "product_by_url": "/api/v1/products?url={url}",
                "supported_sites": "/api/v1/supported-sites",
            },
        }

    app.logger.info("Price Savvy Backend initialized successfully")
    return app
