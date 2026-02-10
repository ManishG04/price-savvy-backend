"""
Price Savvy Backend - Main Entry Point
A Flask-based API for scraping and tracking product prices.
"""
from app import create_app

app = create_app()


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
