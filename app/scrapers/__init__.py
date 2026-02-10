"""
Scrapers module for Price Savvy Backend
"""
from app.scrapers.base_scraper import BaseScraper
from app.scrapers.amazon_scraper import AmazonScraper
from app.scrapers.flipkart_scraper import FlipkartScraper

__all__ = ['BaseScraper', 'AmazonScraper', 'FlipkartScraper']
