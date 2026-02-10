"""
Error handlers for Price Savvy Backend
"""
from flask import jsonify


def register_error_handlers(app):
    """Register error handlers with the Flask app."""
    
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            'success': False,
            'error': 'Bad Request',
            'message': str(error.description) if hasattr(error, 'description') else 'Invalid request'
        }), 400
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'success': False,
            'error': 'Not Found',
            'message': 'The requested resource was not found'
        }), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({
            'success': False,
            'error': 'Method Not Allowed',
            'message': 'The method is not allowed for this endpoint'
        }), 405
    
    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        return jsonify({
            'success': False,
            'error': 'Rate Limit Exceeded',
            'message': 'Too many requests. Please try again later.'
        }), 429
    
    @app.errorhandler(500)
    def internal_server_error(error):
        return jsonify({
            'success': False,
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred'
        }), 500
    
    @app.errorhandler(503)
    def service_unavailable(error):
        return jsonify({
            'success': False,
            'error': 'Service Unavailable',
            'message': 'The service is temporarily unavailable'
        }), 503


class ScraperError(Exception):
    """Base exception for scraper errors."""
    
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class UnsupportedURLError(ScraperError):
    """Exception raised when URL is not supported."""
    
    def __init__(self, url: str):
        message = f"URL not supported: {url}"
        super().__init__(message, status_code=400)


class ScrapingFailedError(ScraperError):
    """Exception raised when scraping fails."""
    
    def __init__(self, url: str, reason: str = None):
        message = f"Failed to scrape URL: {url}"
        if reason:
            message += f" - {reason}"
        super().__init__(message, status_code=500)
