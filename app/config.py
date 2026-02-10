"""
Configuration settings for Price Savvy Backend
Based on PRD requirements for price-savvy scraper
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration class."""

    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-key-change-in-production"
    DEBUG = False
    TESTING = False

    # Database configuration (SQLite as per PRD)
    DATABASE_URL = os.environ.get("DATABASE_URL") or "sqlite:///price_savvy.db"
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Scraper configuration (PRD: 5s timeout, custom User-Agent)
    SCRAPER_TIMEOUT = int(os.environ.get("SCRAPER_TIMEOUT", 5))
    SCRAPER_USER_AGENT = os.environ.get(
        "SCRAPER_USER_AGENT",
        "PriceSavvy/1.0 (+https://github.com/pricesavvy; contact@pricesavvy.com)",
    )

    # Concurrency settings (PRD: max 5 workers)
    MAX_WORKERS = int(os.environ.get("MAX_WORKERS", 5))

    # Rate limiting (PRD: 10 requests/min per IP)
    RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", 10))

    # Per-site request interval (PRD: polite scraping)
    SITE_REQUEST_INTERVAL = float(os.environ.get("SITE_REQUEST_INTERVAL", 1.0))

    # Cache settings (PRD: TTL cache for recent queries)
    CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", 300))  # 5 minutes
    CACHE_MAX_SIZE = int(os.environ.get("CACHE_MAX_SIZE", 100))

    # Pagination defaults (PRD: 20 products per page)
    DEFAULT_PAGE_SIZE = int(os.environ.get("DEFAULT_PAGE_SIZE", 20))
    MAX_PAGE_SIZE = int(os.environ.get("MAX_PAGE_SIZE", 100))

    # Fuzzy matching threshold for deduplication (0-1)
    FUZZY_MATCH_THRESHOLD = float(os.environ.get("FUZZY_MATCH_THRESHOLD", 0.85))

    # Supported e-commerce sites (allowlist)
    ALLOWED_DOMAINS = [
        "amazon.in",
        "amazon.com",
        "flipkart.com",
        "myntra.com",
        "ajio.com",
        "croma.com",
        "tatacliq.com",
        "snapdeal.com",
        "jiomart.com",
        "meesho.com",
    ]

    # Retry settings (PRD: exponential backoff)
    MAX_RETRIES = int(os.environ.get("MAX_RETRIES", 3))
    RETRY_BACKOFF_FACTOR = float(os.environ.get("RETRY_BACKOFF_FACTOR", 2.0))

    # Selenium settings (PRD: Selenium as fallback for dynamic pages)
    SELENIUM_ENABLED = os.environ.get("SELENIUM_ENABLED", "true").lower() == "true"
    SELENIUM_HEADLESS = os.environ.get("SELENIUM_HEADLESS", "true").lower() == "true"
    SELENIUM_TIMEOUT = int(os.environ.get("SELENIUM_TIMEOUT", 10))
    SELENIUM_PAGE_LOAD_TIMEOUT = int(os.environ.get("SELENIUM_PAGE_LOAD_TIMEOUT", 30))

    # Sites that require Selenium (JS-rendered or anti-bot protected)
    SELENIUM_REQUIRED_SITES = [
        "myntra.com",
        "ajio.com",
        "croma.com",
        "tatacliq.com",
        "jiomart.com",
        "meesho.com",
    ]


class DevelopmentConfig(Config):
    """Development configuration."""

    DEBUG = True


class ProductionConfig(Config):
    """Production configuration."""

    DEBUG = False


class TestingConfig(Config):
    """Testing configuration."""

    TESTING = True
    DEBUG = True


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
