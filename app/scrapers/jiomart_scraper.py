"""
JioMart Scraper - Scraper for JioMart (Reliance) products
As per PRD: BeautifulSoup4 for HTML parsing, Selenium for dynamic content
"""

import re
import json
import logging
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from app.scrapers.selenium_scraper import SeleniumScraper

logger = logging.getLogger(__name__)


class JioMartScraper(SeleniumScraper):
    """Scraper for JioMart product pages. Uses Selenium for JS-rendered content."""

    def __init__(self, use_selenium: bool = True, **kwargs):
        """Initialize JioMart scraper with Selenium support."""
        super().__init__(use_selenium=use_selenium, **kwargs)

    @property
    def name(self) -> str:
        return "JioMart"

    @property
    def wait_selector(self) -> Optional[str]:
        """Wait for product cards to load."""
        return ".plp-card-container, .product-card"

    @property
    def supported_domains(self) -> list:
        return ["jiomart.com"]

    @property
    def search_url_template(self) -> str:
        """JioMart search URL template."""
        return "https://www.jiomart.com/search/{query}"

    def _build_search_url(self, query: str) -> str:
        """Build JioMart search URL - JioMart uses path-based search."""
        formatted_query = query.lower().replace(" ", "%20")
        return f"https://www.jiomart.com/search/{formatted_query}"

    def search(self, query: str, max_results: int = 20) -> List[Dict]:
        """
        Search for products on JioMart.

        Args:
            query: Search query string
            max_results: Maximum results to return

        Returns:
            List of product dictionaries
        """
        search_url = self._build_search_url(query)
        try:
            html = self.fetch_page(search_url)
            return self.parse_search_results(html, max_results)
        except Exception as e:
            logger.error(f"JioMart search failed: {e}")
            return []

    def scrape(self, url: str) -> Dict:
        """
        Scrape product information from JioMart.

        Args:
            url: The JioMart product URL.

        Returns:
            Dictionary containing product information.
        """
        html = self.fetch_page(url)
        return self.parse_product(html, url)

    def parse_product(self, html: str, url: str) -> Dict:
        """
        Parse JioMart product page HTML.

        Args:
            html: The HTML content to parse.
            url: The original URL.

        Returns:
            Dictionary containing parsed product information.
        """
        soup = BeautifulSoup(html, "lxml")

        title = self._extract_title(soup)
        price = self._extract_price(soup)
        original_price = self._extract_original_price(soup)
        rating = self._extract_rating(soup)
        image_url = self._extract_image(soup)

        return {
            "source": self.name,
            "url": url,
            "title": title,
            "price": price,
            "original_price": original_price,
            "currency": "INR",
            "rating": rating,
            "reviews": None,
            "availability": "In Stock",
            "image_url": image_url,
            "description": None,
        }

    def parse_search_results(self, html: str, max_results: int = 20) -> List[Dict]:
        """
        Parse JioMart search results page.

        Args:
            html: Search results page HTML
            max_results: Maximum results to return

        Returns:
            List of product dictionaries
        """
        soup = BeautifulSoup(html, "lxml")
        products = []

        # Find product cards
        product_cards = soup.find_all("div", {"class": re.compile(r"plp-card")})
        if not product_cards:
            product_cards = soup.find_all("li", {"class": re.compile(r"product")})

        for card in product_cards[: max_results * 2]:
            try:
                product = self._parse_search_card(card)
                if product and product.get("title") and product.get("url"):
                    products.append(product)
                    if len(products) >= max_results:
                        break
            except Exception as e:
                logger.warning(f"Failed to parse JioMart search card: {e}")

        logger.info(f"Parsed {len(products)} products from JioMart search")
        return products

    def _parse_search_card(self, card: BeautifulSoup) -> Optional[Dict]:
        """Parse a single product card from search results."""
        # Extract link
        link_elem = card.find("a", href=True)
        if not link_elem:
            return None

        href = link_elem.get("href", "")
        url = f"https://www.jiomart.com{href}" if href.startswith("/") else href

        # Extract title
        title_elem = card.find(
            "span", {"class": re.compile(r"product-name")}
        ) or card.find("div", {"class": re.compile(r"plp-card-name")})
        title = title_elem.get_text(strip=True) if title_elem else None

        # Try from image alt
        if not title:
            img = card.find("img", alt=True)
            if img:
                title = img.get("alt", "")

        if not title:
            return None

        # Extract price
        price = None
        price_elem = card.find("span", {"class": re.compile(r"price|final")})
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            price = re.sub(r"[^\d]", "", price_text)

        # Also try finding ₹
        if not price:
            price_text = card.find(string=lambda t: t and "₹" in t if t else False)
            if price_text:
                price = re.sub(r"[^\d]", "", price_text)

        # Extract original price
        original_elem = card.find("span", {"class": re.compile(r"line-through|mrp")})
        original_price = original_elem.get_text(strip=True) if original_elem else None

        # Extract image
        img_elem = card.find("img")
        image_url = None
        if img_elem:
            image_url = img_elem.get("src") or img_elem.get("data-src")

        return {
            "source": self.name,
            "url": url,
            "title": title,
            "price": price,
            "original_price": original_price,
            "currency": "INR",
            "rating": None,
            "reviews": None,
            "image_url": image_url,
        }

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract product title."""
        title_elem = soup.find("h1") or soup.find(
            "span", {"class": re.compile(r"product-name")}
        )
        return title_elem.get_text(strip=True) if title_elem else None

    def _extract_price(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract current price."""
        price_elem = soup.find(
            "span", {"class": re.compile(r"final-price|selling-price")}
        )
        if price_elem:
            return re.sub(r"[^\d]", "", price_elem.get_text(strip=True))
        return None

    def _extract_original_price(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract original price."""
        elem = soup.find("span", {"class": re.compile(r"line-through|mrp")})
        if elem:
            return elem.get_text(strip=True)
        return None

    def _extract_rating(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract product rating."""
        rating_elem = soup.find("span", {"class": re.compile(r"rating")})
        if rating_elem:
            text = rating_elem.get_text(strip=True)
            match = re.search(r"(\d+\.?\d*)", text)
            if match:
                return match.group(1)
        return None

    def _extract_image(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract product image URL."""
        img = soup.find("img", {"class": re.compile(r"product-image|main-image")})
        if img:
            return img.get("src") or img.get("data-src")
        return None
