"""
Scrapers module for Price Savvy Backend
"""

from app.scrapers.base_scraper import BaseScraper
from app.scrapers.selenium_scraper import SeleniumScraper
from app.scrapers.selenium_driver import SeleniumDriver, is_selenium_available
from app.scrapers.amazon_scraper import AmazonScraper
from app.scrapers.flipkart_scraper import FlipkartScraper
from app.scrapers.myntra_scraper import MyntraScraper
from app.scrapers.ajio_scraper import AjioScraper
from app.scrapers.croma_scraper import CromaScraper
from app.scrapers.tatacliq_scraper import TataCliqScraper
from app.scrapers.snapdeal_scraper import SnapdealScraper
from app.scrapers.jiomart_scraper import JioMartScraper
from app.scrapers.meesho_scraper import MeeshoScraper

__all__ = [
    "BaseScraper",
    "SeleniumScraper",
    "SeleniumDriver",
    "is_selenium_available",
    "AmazonScraper",
    "FlipkartScraper",
    "MyntraScraper",
    "AjioScraper",
    "CromaScraper",
    "TataCliqScraper",
    "SnapdealScraper",
    "JioMartScraper",
    "MeeshoScraper",
]
